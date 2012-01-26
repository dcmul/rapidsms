#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
from datetime import timedelta
from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.exceptions import ParseError, BadValue, Inapplicable
from childcount.models import Patient, Encounter
from childcount.models.reports import BirthReport
from childcount.models.reports import AppointmentReport
from childcount.forms.utils import MultipleChoiceField


class BirthForm(CCForm):
    """ Register children under 28 days

    Params:
        * Mom Health ID
        * delivered in health facility
        * weight(kg)(optional)
    """

    KEYWORDS = {
        'en': ['bir', 'birth'],
        'rw': ['bir', 'birth'],
        'fr': ['bir', 'birth'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_PATIENT
    MIN_BIRTH_WEIGHT = 1
    MAX_BIRTH_WEIGHT = 6
    MIN_GUARDIAN_AGE = 10
    UNKNOWN_MOTHER = {'en': 'U', 'fr': 'I', 'rw': 'U', 'default': 'U'}

    def process(self, patient):

        cd_field = MultipleChoiceField()
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_YES, 'Y')
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_NO, 'N')
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_UNKNOWN, 'U')
        cd_field.add_choice('rw', BirthReport.CLINIC_DELIVERY_YES, 'O')
        cd_field.add_choice('rw', BirthReport.CLINIC_DELIVERY_NO, 'N')
        cd_field.add_choice('rw', BirthReport.CLINIC_DELIVERY_UNKNOWN, 'I')
        cd_field.add_choice('fr', BirthReport.CLINIC_DELIVERY_YES, 'O')
        cd_field.add_choice('fr', BirthReport.CLINIC_DELIVERY_NO, 'N')
        cd_field.add_choice('fr', BirthReport.CLINIC_DELIVERY_UNKNOWN, 'I')

        try:
            br = BirthReport.objects.get(encounter=self.encounter)
        except BirthReport.DoesNotExist:
            br = BirthReport(encounter=self.encounter)
            overwrite = False
        else:
            br.reset()
            overwrite = True
        br.form_group = self.form_group

        days, weeks, months = patient.age_in_days_weeks_months(\
            self.encounter.encounter_date.date())
        humanised = patient.humanised_age()

        if days > 90:
            raise Inapplicable(_(u"Patient is %(age)s old. You can not " \
                                  "submit birth reports for patients over " \
                                  "90 days old.") % {'age': humanised})

        if BirthReport.objects.filter(encounter__patient=patient).count() > 0 \
                                                             and not overwrite:
            br = BirthReport.objects.filter(encounter__patient=patient)[0]
            raise Inapplicable(_(u"A birth report for %(p)s was already " \
                                  "submited by %(chw)s.") % \
                                  {'p': patient, 'chw': br.chw()})

        if len(self.params) < 3:
            raise ParseError(_(u"Not enough info. Expected: " \
                                "| Mom Health ID | delivered in health " \
                                "facility | weight(kg)(optional) |"))

        cd_field.set_language(self.chw.language)
        lang = self.message.reporter.language

        # Mother field
        mother = self.params[1]
        is_unknown_mother = False
        if lang not in self.UNKNOWN_MOTHER:
            print "Using default value, Need to define value for lang", lang
            is_unknown_mother = (mother.lower() == \
                                    self.UNKNOWN_MOTHER['default'].lower())
        else:
            is_unknown_mother = (mother.lower() == \
                                        self.UNKNOWN_MOTHER[lang].lower())
        if is_unknown_mother:
            patient.mother = None
        else:
            try:
                patient.mother = Patient.objects.get( \
                                                health_id__iexact=mother)
            except Patient.DoesNotExist:
                raise BadValue(_(u"Could not find mother / guardian " \
                                    "with health ID %(id)s. You must " \
                                    "register the mother first.") % \
                                    {'id': mother})
            if patient.mother < self.MIN_GUARDIAN_AGE:
                raise BadValue(_(u"The mother / guardian you specified " \
                                    "is too young to be a mother." \
                                    "(%(hh)s)") % {'hh': patient.household})

        clinic_delivery = self.params[2]
        if not cd_field.is_valid_choice(clinic_delivery):
            raise BadValue(_(u"| Delivered in health facility? | must be " \
                              "%(choices)s.") % \
                              {'choices': cd_field.choices_string()})
        cd_db = cd_field.get_db_value(clinic_delivery)

        weight = None
        print self.params
        print len(self.params)
        if len(self.params) > 3:
            regex = r'(?P<w>\d+(\.?\d*)?).*'
            match = re.match(regex, self.params[3])
            if match:
                weight = float(match.groupdict()['w'])
                if weight > self.MAX_BIRTH_WEIGHT:
                    raise BadValue(_(u"Birth weight can not be greater than " \
                                      "%(max)skg.") % \
                                     {'max': self.MAX_BIRTH_WEIGHT})
                if weight < self.MIN_BIRTH_WEIGHT:
                    raise BadValue(_(u"Birth weight can not be less than " \
                                      "%(min)skg.") % \
                                     {'min': self.MIN_BIRTH_WEIGHT})
            else:
                raise ParseError(_(u"Unkown value. Weight should be a number"))

        if cd_db == BirthReport.CLINIC_DELIVERY_YES:
            cd_string = _(u"Delivered in health facility")
        elif cd_db == BirthReport.CLINIC_DELIVERY_NO:
            cd_string = _(u"Home delivery")
        elif cd_db == BirthReport.CLINIC_DELIVERY_UNKNOWN:
            cd_string = _(u"Unkown delivery location")

        self.response = cd_string
        if weight:
            self.response += _(", %(weight)skg birth weight") % \
                              {'weight': weight}

        br.clinic_delivery = cd_db
        br.weight = weight
        br.save()
        patient.save()

        #is mother hiv exposed?
        if patient.mother.hiv_status:
            #mark child as hiv exposed
            patient.hiv_exposed = True
            patient.save()

            #create an appointment 6 weeks from DOB
            week_six = patient.dob + timedelta(weeks=6)
            aptr = AppointmentReport(encounter=self.encounter)
            aptr.appointment_date = week_six
            aptr.status = AppointmentReport.STATUS_OPEN
            aptr.notification_sent = False
            aptr.save()

        #setup reminders
        br.setup_reminders()
