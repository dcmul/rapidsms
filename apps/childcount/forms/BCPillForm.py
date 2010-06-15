#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin


from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.models.reports import BCPillReport
from childcount.models import Encounter
from childcount.exceptions import ParseError


class BCPillForm(CCForm):
    KEYWORDS = {
        'en': ['l'],
        'fr': ['l'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_HOUSEHOLD

    def process(self, patient):
        if len(self.params) < 2:
            raise ParseError(_(u"Not enough info. Expected: number of pills " \
                                "given."))

        try:
            bcpr = BCPillReport.objects.get(encounter=self.encounter)
        except BCPillReport.DoesNotExist:
            bcpr = BCPillReport(encounter=self.encounter)
        bcpr.form_group = self.form_group

        if not self.params[1].isdigit():
            raise ParseError(_(u"Number of pills " \
                                "given must be " \
                                "entered a number."))

        bcpr.pills = int(self.params[1])
        bcpr.save()
 
        self.response = _(u"%(pills)d pills given.") % {'pills':bcpr.pills}
