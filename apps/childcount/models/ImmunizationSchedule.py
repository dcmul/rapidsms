#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

import datetime
import reversion

from django.db import models
from django.utils.translation import ugettext as _

from childcount.models import Patient

class ImmunizationNotification(models.Model):

    class Meta:
        app_label = 'childcount'
        db_table = 'cc_immunnotif'
        verbose_name = _(u"Immunization Notification")
        verbose_name_plural = _(u"Immunization Notifications")
        unique_together = (("patient", "immunization"),)

    patient = models.ForeignKey('Patient')
    immunization = models.ForeignKey('ImmunizationSchedule', \
                                        verbose_name=_("Immunization"))
    notify_on = models.DateTimeField(_(u"Notify on"), blank=True, null=True, \
                                 help_text=_(u"When to notify"))
    notified_on = models.DateTimeField(_(u"Notified on"), blank=True, \
                                 null=True, help_text=_(u"Notified on"))

    def __unicode__(self):
        return u" %s %s " % (self.patient, self.immunization)

reversion.register(ImmunizationNotification)


class ImmunizationSchedule(models.Model):

    class Meta:
        app_label = 'childcount'
        db_table = 'cc_immunsched'
        verbose_name = _(u"Immunization Schedule")
        verbose_name_plural = _(u"Immunization Schedules")

    PERIOD_DAYS = 'DAYS'
    PERIOD_WEEKS = 'WEEKS'
    PERIOD_MONTHS = 'MONTHS'

    PERIOD_CHOICES = (
        (PERIOD_DAYS, _(u"Days")),
        (PERIOD_WEEKS, _(u"Weeks")),
        (PERIOD_MONTHS, _(u"Months")))

    period = models.PositiveIntegerField(_(u"Period"), \
                                 help_text=_(u"Time period after birth"))
    period_type = models.CharField(_(u"Period type"), max_length=10,\
                                    choices=PERIOD_CHOICES)
    immunization = models.CharField(_(u"Immunization"), max_length=100, \
                                 help_text=_(u"Name of the immunization"))

    def __unicode__(self):
        return _(u"After %(period_nb)s %(period_type)s: %(immun)s") \
                 % (self.period, self.period_type, \
                    self.immunization)

    @classmethod
    def generate_schedule(cls, kid):
        'Generate immunization '
        schedule = cls.objects.all()
        for period in schedule:
            patient_dob = kid.dob
            notify_on = datetime.today()
            immunization = ImmunizationNotification()
            if not ImmunizationNotification.objects.filter(patient=kid, \
                                                        immunization=period):
                immunization.patient = self
                immunization.immunization = period
                if period.period_type == cls.PERIOD_DAYS:
                    notify_on = patient_dob + timedelta(period.period)
                    immunization.notify_on = notify_on
                if period.period_type == cls.PERIOD_WEEKS:
                    notify_on = patient_dob + timedelta(period.period * 7)
                    immunization.notify_on = notify_on
                if period.period_type == cls.PERIOD_MONTHS:
                    notifyon = patient_dob + timedelta(30.4375 * period.period)
                    immunization.notify_on = notifyon

                immunization.save()


reversion.register(ImmunizationSchedule)


