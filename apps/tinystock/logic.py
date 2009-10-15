# coding=utf-8

from models import KindOfItem, Item, StockItem, TransferLog
from exceptions import *
from django.utils.translation import ugettext as _
from datetime import datetime

def item_stock_for(store):
    ''' store is the provider '''
    items   = []
    stocks  = StockItem.objects.filter(peer=store)
    for stock in stocks:
        items.append({'item': stock.item, 'quantity': stock.quantity})

    return items

def add_stock_for_item(receiver, item, quantity):
    ''' Add to stock quantity for a pharmacist '''

    # retrieve or create StockItem for receiver
    # need to make it smarter to check to make sure sku item exists
    try:
        receiver_stock      = StockItem.by_peer_item(peer=receiver, item=item)
    except StockItem.DoesNotExist:
        receiver_stock      = StockItem.new_by_peer_item_qty(peer=receiver, item=item, quantity=0)
        receiver_stock.save()
        
    log = TransferLog(sender=receiver, receiver=receiver, item=item, quantity=quantity, date=datetime.now())

    # actual transfer
    try:
        receiver_stock.quantity += quantity
        receiver_stock.save()
        log.save()
    
    except Exception, e:
        raise e

    return log



def transfer_item(sender, receiver, item, quantity):
    ''' Transfer an arbitrary quantity of goods between to StoreProvider '''
    try:
        sender_stock        = StockItem.by_peer_item(peer=sender, item=item)
    except StockItem.DoesNotExist:
        # Store has no such item in stock
        raise ItemNotInStore

    # Check if Store has enough items to share
    if sender_stock.quantity < quantity:
        raise NotEnoughItemInStock

    # retrieve or create StockItem for receiver    
    try:
        receiver_stock      = StockItem.by_peer_item(peer=receiver, item=item)
    except StockItem.DoesNotExist:
        receiver_stock      = StockItem.new_by_peer_item_qty(peer=receiver, item=item, quantity=0)
        #StockItem(peer=receiver, item=item, quantity=0)
        receiver_stock.save()

    log = TransferLog(sender=sender, receiver=receiver, item=item, quantity=quantity, date=datetime.now())

    # actual transfer
    try:
        sender_stock.quantity   -= quantity
        receiver_stock.quantity += quantity
        sender_stock.save()
        receiver_stock.save()
        log.save()
    except Exception, e:
        raise e

    return log


def add_item(sku, code, kind, name):
    item    = Item(sku=sku, code=code, kind=kind, name=name)
    item.save()
    return item

def cancel_transfer(transac):
    ''' Transfer back goods in opposite way.
        Returns False if impossible (goods not present)'''

    # if transfer was an addition, remove goods
    if transac.sender == transac.receiver:
        quantity    = -(transac.quantity)
    else:
        quantity    = transac.quantity

    try:
        log = transfer_item(sender=transac.receiver, receiver=transac.sender, item=transac.item, quantity=quantity)
        transac.status  = TransferLog.STATUS_CANCELLED
        transac.save()
    except Exception, e:
        transac.status  = TransferLog.STATUS_CONFLICT
        transac.save()
        raise e
    return log
    

    
    
