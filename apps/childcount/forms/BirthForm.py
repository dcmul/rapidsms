#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.exceptions import ParseError, BadValue, Inapplicable
from childcount.models import Encounter
from childcount.models.reports import BirthReport
from childcount.forms.utils import MultipleChoiceField


class BirthForm(CCForm):
    KEYWORDS = {
        'en': ['bir', 'birth'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_PATIENT
    MIN_BIRTH_WEIGHT = 1
    MAX_BIRTH_WEIGHT = 6

    def process(self, patient):

        cd_field = MultipleChoiceField()
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_YES, 'Y')
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_NO, 'N')
        cd_field.add_choice('en', BirthReport.CLINIC_DELIVERY_UNKOWN, 'U')

        try:
            br = BirthReport.objects.get(encounter=self.encounter)
        except BirthReport.DoesNotExist:
            br = BirthReport(encounter=self.encounter)
            overwrite = False
        else:
            br.reset()
            overwrite = True
        br.form_group = self.form_group

        days, weeks, months = patient.age_in_days_weeks_months()
        humanised = patient.humanised_age()
        if days > 28:
            raise Inapplicable(_(u"Patient is %(age)s old. You cannot " \
                                  "submit birth reports for patients over " \
                                  "28 days old") % {'age': humanised})

        if BirthReport.objects.filter(encounter__patient=patient).count() > 0 \
                                                             and not overwrite:
            br = BirthReport.objects.filter(encounter__patient=patient)[0]
            raise Inapplicable(_(u"A birth report for %(p)s was already " \
                                  "submited by %(chw)s") % \
                                  {'p': patient, 'chw': br.chw()})

        if len(self.params) < 2:
            raise ParseError(_(u"Not enough information, expected: " \
                                "|delivered in health facility| " \
                                "weight(kg)(optional)"))

        cd_field.set_language(self.chw.language)
        clinic_delivery = self.params[1]
        if not cd_field.is_valid_choice(clinic_delivery):
            raise BadValue(_(u"|Delivered in health facility?| must be " \
                              "%(choices)s") % \
                              {'choices': cd_field.choices_string()})
        cd_db = cd_field.get_db_value(clinic_delivery)

        weight = None
        if len(self.params) > 2:
            regex = r'(?P<w>\d+(\.?\d*)?).*'
            match = re.match(regex, self.params[2])
            if match:
                weight = float(match.groupdict()['w'])
                if weight > self.MAX_BIRTH_WEIGHT:
                    raise BadValue(_(u"Birth weight can not be greater than " \
                                      "%(max)skg") % \
                                     {'max': self.MAX_BIRTH_WEIGHT})
                if weight < self.MIN_BIRTH_WEIGHT:
                    raise BadValue(_(u"Birth weight can not be less than " \
                                      "%(min)skg") % \
                                     {'min': self.MIN_BIRTH_WEIGHT})
            else:
                raise ParseError(_(u"Unkown value. Weight should be a number"))


        if cd_db == BirthReport.CLINIC_DELIVERY_YES:
            cd_string = _(u"Delivered in health facility")
        elif cd_db == BirthReport.CLINIC_DELIVERY_NO:
            cd_string = _(u"Home delivery")
        elif cd_db == BirthReport.CLINIC_DELIVERY_UNKOWN:
            cd_string = _(u"Unkown delivery location")

        self.response = cd_string
        if weight:
            self.response += _(", %(weight)skg birth weight") % \
                              {'weight': weight}

        br.clinic_delivery = cd_db
        br.weignt = weight
        br.save()