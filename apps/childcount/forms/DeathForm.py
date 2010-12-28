#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
import time
from datetime import date

from django.utils.translation import ugettext as _
from ethiopian_date import EthiopianDateConverter

from childcount.forms import CCForm
from childcount.exceptions import BadValue, ParseError, InvalidDOB
from childcount.exceptions import Inapplicable
from childcount.models import Configuration
from childcount.models.reports import DeathReport
from childcount.models import Patient, Encounter
from childcount.utils import DOBProcessor


class DeathForm(CCForm):
    """ Register a death

    Params:
        * date of death
    """

    KEYWORDS = {
        'en': ['dda'],
        'fr': ['dda'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_PATIENT

    def process(self, patient):
        if len(self.params) < 2:
            raise ParseError(_(u"Not enough info. Expected: date of death."))

        try:
            dr = DeathReport.objects.get(encounter=self.encounter)
        except DeathReport.DoesNotExist:
            dr = DeathReport(encounter=self.encounter)
            overwrite = False
        else:
            dr.reset()
            overwrite = True
        dr.form_group = self.form_group

        if DeathReport.objects.filter(encounter__patient=patient).count() > 0:
            dr = DeathReport.objects.filter(encounter__patient=patient)[0]
            raise Inapplicable(_(u"A death report for %(p)s was already " \
                                  "submited by %(chw)s.") % \
                                  {'p': patient, 'chw': dr.chw()})

        # import ethiopian date variable
        try:
            is_ethiopiandate = bool(Configuration.objects \
                                .get(key='inputs_ethiopian_date').value)
        except (Configuration.DoesNotExist, TypeError):
            is_ethiopiandate = False

        dod_str = ' '.join(self.params[1:])
        try:
            dod, variance = DOBProcessor.from_dob(self.chw.language, dod_str, \
                                                  self.date.date())
        except InvalidDOB:
            raise BadValue(_(u"Could not understand date of death: " \
                             "%(dod)s.") % \
                             {'dod': dod_str})

        # convert dod to gregorian before saving to DB
        if is_ethiopiandate and not variance:
            dod = EthiopianDateConverter.date_to_gregorian(dod)

        dr.death_date = dod
        dr.save()

        patient.status = Patient.STATUS_DEAD
        patient.save()

        self.response = _("Died on %(dod)s") % {'dod': dod}
