# coding=utf-8

import rapidsms
from apps.tinystock.logic import *
from apps.tinystock.exceptions import *
from models import Facility, Provider, Patient
from apps.tinystock.models import StoreProvider, KindOfItem, Item, StockItem
from django.utils.translation import ugettext as _
from rapidsms.parsers.keyworder import Keyworder
from utils import *
from datetime import datetime
from apps.reporters.models import Reporter, Role, ReporterGroup
from apps.locations.models import Location

class HandlerFailed (Exception):
    pass

class MalformedRequest (Exception):
    pass

def registered (func):
    def wrapper (self, message, *args):
        if message.persistant_connection.reporter:
            return func(self, message, *args)
        else:
            message.respond(_(u"Sorry, only registered users can access this program."))
            return True
    return wrapper

def admin (func):
    def wrapper (self, message, *args):
        reporter = message.persistant_connection.reporter
        if reporter and ReporterGroup.objects.get(title='admin') in reporter.groups.only():
            return func(self, message, *args)
        else:
            message.respond(_(u"Sorry, only administrators of the system can perform this action."))
            return False
    return wrapper

class App (rapidsms.app.App):

    keyword     = Keyworder()
    # debug! shouldn't exist. sets the char to identify drugs
    # in sms. used because httptester doesn'h handles #. use $ instead
    drug_code   = '$'

    def start (self):
        self.backend    = self._router.backends.pop()

    def parse (self, message):
        """Parse and annotate messages in the parse phase."""
        pass

    def handle (self, message):
        try:
            func, captures = self.keyword.match(self, message.text)
        except TypeError:
            # didn't find a matching function
            return False
        try:
            handled = func(self, message, *captures)
        except HandlerFailed, e:
            print e
            send_message(backend=self.backend, sender=Member.system(), receivers=message.peer, content=e, action='err_plain_notif', overdraft=True, fair=True)
            handled = True
        except Exception, e:
            print e
            message.respond(_(u"An error has occured (%(e)s).") % {'e': e})
            raise
        message.was_handled = bool(handled)
        return handled

    @keyword(r'join (\w+) (\w+) (.+)')
    def register_provider (self, message, role, clinic, name):
        ''' Adds people into the system 
            JOIN CHW PASSWORD LAST FIRST ALIAS'''
        
        # If error in role, assume CHW
        try:
            role    = Role.objects.get(code=role.lower())
        except Role.DoesNotExist: 
            role    = Role.objects.get(code='chw')

        # retrieve clinic
        try:
            clinic      = Location.objects.get(code=clinic.lower())
        except Location.DoesNotExist:
            clinic      = None
        
        # PHA _must_ be affiliated to a Clinic
        if role.code == 'pha' and clinic == None:
            message.respond(_(u"Registration Failed. PHA needs correct clinic ID. '%(input)s' is not.") % {'input': clinic})
            return True

        # Create provier
        try:
            alias, fn, ln = Provider.parse_name(name)
            provider = Provider(alias=alias, first_name=fn, last_name=ln, location=clinic, role=role)
            provider.save()
            
            # attach the reporter to the current connection
            message.persistant_connection.reporter = provider
            message.persistant_connection.save()
        except Exception, e:
            message.respond(_(u"Registration failed: %(error)s") % {'error': e.args})

        # send notifications
        message.respond(_(u"SUCCESS. %(prov)s has been registered with alias %(al)s.") % {'prov': provider.display_full(), 'al': provider.alias})
        
        if provider.connection():
            message.forward(provider.connection().identity, _(u"Welcome %(prov)s. You have been registered with alias %(al)s.") % {'prov': provider.display_full(), 'al': provider.alias})
    
        return True

    def do_transfer_drug(self, message, sender, receiver, item, quantity):
        
        log = transfer_item(sender=sender, receiver=receiver, item=item, quantity=int(quantity))
        
        if receiver.connection():
            message.forward(receiver.connection().identity, "CONFIRMATION #%(d)s-%(sid)s-%(rid)s-%(lid)s You have received %(quantity)s %(item)s from %(sender)s. If not correct please reply: CANCEL %(lid)s" % {
                'quantity': quantity,
                'item': item.name,
                'sender': sender.display_full(),
                'd': log.date.strftime("%d%m%y"),
                'sid': sender.id,
                'rid': receiver.id,
                'lid': log.id
            })

        message.respond("CONFIRMATION #%(d)s-%(sid)s-%(rid)s-%(lid)s You have sent %(quantity)s %(item)s to %(receiver)s. If not correct please reply: CANCEL %(lid)s" % {
            'quantity': quantity,
            'item': item.name,
            'receiver': receiver.display_full(),
            'd': log.date.strftime("%d%m%y"),
            'sid': sender.id,
            'rid': receiver.id,
            'lid': log.id
        })
        return True

    @keyword(r'dist \@(\w+) (\w+) (\d+)')
    @registered
    def transfer_clinic_chw (self, message, receiver, code, quantity):
        ''' Transfer Drug from Clinic to CHW or CHW to Clinic
            DIST @mdiallo #001 10'''

        sender      = StoreProvider.cls().objects.get(id=message.persistant_connection.reporter.id)
        receiver    = StoreProvider.cls().objects.get(alias=receiver.lower())
        item        = Item.by_code(code)
        if item == None or sender == None or receiver == None:
            message.respond(_(u"Distribution request failed. Either Item ID or CHW alias is wrong."))
            return True

        try:
            return self.do_transfer_drug(message, sender, receiver, item, quantity)
        except ItemNotInStore:
            message.respond(_(u"Distribution request failed. You do not have %(med)s") % {'med': item})
            return True
        except NotEnoughItemInStock:
            message.respond(_(u"Distribution request failed. You can't transfer %(q)s %(it)s to %(rec)s because you only have %(stk)s.") % {'q': quantity, 'it': item.name, 'rec': receiver.display_full(), 'stk': StockItem.objects.get(peer=sender, item=item).quantity})
            return True

    @keyword(r'add (\w+) (\d+) (.+)')
    @admin
    def add_stock (self, message, code, quantity, note):
        
        ''' Add stock for item. Used by main drug distribution point'''
        
        sender      = StoreProvider.cls().objects.get(id=message.persistant_connection.reporter.id)
        
        # only PHA can add drugs
        try:
            no_pha  = not sender.direct().role == Role.objects.get(code='pha')
        except:
            no_pha  = True        

        if no_pha:
            message.respond(_(u"Addition request failed. Only PHA can perform such action."))
            return True

        receiver    = sender
        item        = Item.by_code(code)
        if item == None or sender == None or receiver == None:
            message.respond(_(u"Addition request failed. Either Item ID or CHW alias is wrong."))
            return True
        
        try:
            log = add_stock_for_item(receiver=receiver, item=item, quantity=int(quantity))
        
            message.respond("CONFIRMATION #%(d)s-%(sid)s-%(lid)s You have added %(quantity)s %(item)s to your stock. If not correct please reply: CANCEL %(lid)s" % {
            'quantity': quantity,
            'item': item.name,
            'receiver': receiver.display_full(),
            'd': log.date.strftime("%d%m%y"),
            'sid': sender.id,
            'rid': receiver.id,
            'lid': log.id
            })
        except:
            pass

        return True

    def parse_sku_quantities(self, sku_quantities):
        couples  = sku_quantities.split(" %s" % self.drug_code)
        skq = {}
        try:
            for couple in couples:
                x = couple.split(" ")
                code = x[0].replace(self.drug_code, "")
                item = Item.by_code(code)
                if skq.has_key(code) or item == None:
                    raise MalformedRequest
                skq[code]   = {'code': code, 'quantity': int(x[1]), 'item': item}
            return skq
        except IndexError:
            raise MalformedRequest

    @keyword(r'cdist \@(\w+)(.+)')
    @registered
    def bulk_transfer_clinic_chw (self, message, receiver, sku_quantities):
        ''' Transfer Multiple Drugs from Clinic to CHW
            CDIST @mdiallo #001 10 #004 45 #007 32'''

        sender      = StoreProvider.cls().objects.get(id=message.persistant_connection.reporter.id)
        receiver    = StoreProvider.cls().objects.get(alias=receiver.lower())

        if sku_quantities == None or sender == None or receiver == None:
            message.respond(_(u"Distribution request failed. Either Item IDs or CHW alias is wrong."))
            return True

        try:
            sq  = self.parse_sku_quantities(sku_quantities)
        except MalformedRequest:
            message.respond(_(u"Distribution failed. Syntax error in drugs/quantities statement."))
            return True
        
        success = []
        failures= []
        for code in sq.itervalues():
            try:
                self.do_transfer_drug(message, sender, receiver, code['item'], code['quantity'])
                success.append(code)
            except (NotEnoughItemInStock, ItemNotInStore, Exception):
                failures.append(code)
                continue
        
        if failures.__len__() == 0:
            message.respond(_(u"SUMMARY: Multiple Drugs Distribution went through successfuly."))
            return True
        
        if success.__len__() == 0:
            message.respond(_(u"SUMMARY: complete FAILURE. Multiple Drugs Distribution went wrong on all items."))
            return True

        # some failed, some went trough
        details = u""
        for fail in failures:
            details += u"%s, " % fail['item'].name
        details = details[:-2]
        message.respond(_(u"SUMMARY: Some items couldn't be transfered: %(detail)s") % {'detail': details})
        return True

    @keyword(r'disp (\w+) (\w+) ([mMfF]) ([0-9\.]+[m|y]?) (\w+) (\d+)')
    @registered
    def dispense_drug_patient (self, message, first, last, gender, age, code, quantity):

        age     = Patient.age_from_str(age)
        gender  = Patient.SEXE_MALE if gender.upper() == 'M' else Patient.SEXE_FEMALE
        receiver= Patient(first_name=first, last_name=last, sexe=gender,age=age)
        receiver.save()
        sender      = StoreProvider.cls().objects.get(id=message.persistant_connection.reporter.id)
        item        = Item.by_code(code)

        if item == None or sender == None or receiver == None:
            message.respond(_(u"Dispense request failed. Either Item ID or Patient datas are wrong."))
            return True

        try:
            log = transfer_item(sender=sender, receiver=receiver, item=item, quantity=int(quantity))
        except ItemNotInStore:
            message.respond(_(u"Dispense request failed. You do not have %(med)s") % {'med': item})
            return True
        except NotEnoughItemInStock:
            message.respond(_(u"Dispense request failed. You can't dispense %(q)s %(it)s to %(rec)s because you only have %(stk)s.") % {'q': quantity, 'it': item.name, 'rec': receiver.display_full(), 'stk': StockItem.objects.get(peer=sender, item=item).quantity})
            return True

        message.respond("CONFIRMATION #%(d)s-%(sid)s-%(rid)s-%(lid)s You have dispensed %(quantity)s %(item)s to %(receiver)s. If not correct please reply: CANCEL %(lid)s" % {
            'quantity': quantity,
            'item': item.name,
            'receiver': receiver.display_full(),
            'd': log.date.strftime("%d%m%y"),
            'sid': sender.id,
            'rid': receiver.id,
            'lid': log.id
        })
        return True
        

    def stock_for(self, message, provider):
        if provider == None:
            return False
        msg = stock_answer(provider)
        message.respond(msg)
        return msg

    @keyword(r'stock \@(\w+)')
    @registered
    def request_stock (self, message, target):
        ''' Get stock status for someone.
            /!\ limited to providers ; no locations or others
            STOCK @mdiallo'''
        
        provider    = Provider.objects.get(alias=target.lower())
        return self.stock_for(message, provider)

    @keyword(r'stock')
    @registered
    def request_self_stock (self, message):
        ''' Get stock status for a store
            STOCK'''
        
        provider    = StoreProvider.objects.get(id=message.persistant_connection.reporter.id)
        return self.stock_for(message, provider)

    @keyword(r'cancel (\d+)')
    @registered
    def cancel_request (self, message, cancel_id):
        ''' Cancel a transfer request
            CANCEL 908432'''
        
        # retrieve transaction
        try:
            log = TransferLog.objects.get(id=int(cancel_id))
        except TransferLog.DoesNotExist:
            message.respond(_(u"Cancellation failed. Provided transaction ID (%(lid)s) is wrong.") % {'lid': cancel_id})
            return True

        # Check request is legitimate
        try:
            peer    = StoreProvider.objects.get(id=message.persistant_connection.reporter.id)
        except:
            peer    = None
        if peer == None or (log.sender, log.receiver).count(peer) == 0:
            message.respond(_("Cancellation failed. With all due respect, you are not allowed to perform this action."))
            return True

        # Check is transfer hasn't already been cancelled
        if (TransferLog.STATUS_CANCELLED, TransferLog.STATUS_CONFLICT).count(log.status) != 0 :
            message.respond(_("Cancellation failed. Transfer #%(lid)s dated %(date)s has already been cancelled or is in conflict.") % {'lid': log.id, 'date': log.date.strftime("%b %d %y %H:%M")})
            return True
        
        # cancellation attempt
        other_peer  = log.receiver if peer == log.sender else log.sender

        # if peer is a patient, don't send messages
        try:
            peer_is_patient = not other_peer.connection()
        except:
            peer_is_patient = True

        try:
            cancel_transfer(log)
            msg = _(u"CANCELLED Transfer #%(lid)s dated %(date)s by request of %(peer)s. Please forward conflict to Drug Store Head.") % {'lid': log.id, 'date': log.date.strftime("%b %d %y %H:%M"), 'peer': peer.direct().display_full()}
            message.respond(msg)
            if not peer_is_patient:
                message.forward(other_peer.connection().identity, msg)
        except (ItemNotInStore, NotEnoughItemInStock):
            # goods has been transfered elsewhere.
            msg = _(u"Cancellation failed. %(peer)s has started distributing drugs from transaction #%(lid)s. Contact Drug Store Head.") % {'lid': log.id, 'peer': log.receiver.direct().display_full()}
            message.respond(msg)
            if not peer_is_patient:
                message.forward(other_peer.connection().identity, msg)
        except Provider.DoesNotExist:
            pass
        return True

    def outgoing (self, message):
        pass

