#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

'''ChildCount Models

Case - Patient/Child model

CaseNote - case notes model
'''

from django.db import models
from django.utils.translation import ugettext_lazy as _

from datetime import datetime, timedelta, date

from reporters.models import Reporter
from locations.models import Location


class Case(models.Model):

    '''Holds the patient details, properties and methods related to it'''

    class Meta:
        app_label = "childcount"

    STATUS_ACTIVE = 1
    STATUS_INACTIVE = 0
    STATUS_DEAD = -1

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Alive"),
        (STATUS_INACTIVE, "Relocated"),
        (STATUS_DEAD, "Dead"))

    GENDER_CHOICES = (
        ('M', _('Male')),
        ('F', _('Female')))

    ref_id = models.IntegerField(_('Case ID #'), null=True, db_index=True)
    first_name = models.CharField(max_length=255, db_index=True)
    last_name = models.CharField(max_length=255, db_index=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, \
                              null=True, blank=True)
    dob = models.DateField(_('Date of Birth'), null=True, blank=True)
    estimated_dob = models.NullBooleanField(null=True, blank=True)
    guardian = models.CharField(max_length=255, null=True, blank=True)
    guardian_id = models.CharField(max_length=255, null=True, blank=True)
    mobile = models.CharField(max_length=16, null=True, blank=True)
    reporter = models.ForeignKey(Reporter, db_index=True)
    location = models.ForeignKey(Location, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=STATUS_CHOICES, \
                                      default=STATUS_ACTIVE)

    def get_absolute_url(self):
        '''return absolute url of a case'''
        return "/case/%s/" % self.id

    def __unicode__(self):
        return "#%d" % self.ref_id

    def _luhn(self, x):
        '''Get a reference number given a number - usually the primary key.'''
        parity = True
        sum = 0
        for c in reversed(str(x)):
            n = int(c)
            if parity:
                n *= 2
                if n > 9:
                    n -= 9
            sum += n
        return x * 10 + 15 - sum % 10

    def save(self, *args):
        if not self.id:
            self.created_at = self.updated_at = datetime.now()
        else:
            self.updated_at = datetime.now()
        super(Case, self).save(*args)
        if not self.ref_id:
            self.ref_id = self._luhn(self.id)
            super(Case, self).save(*args)

    def get_dictionary(self):
        '''get a dictionary of a case details'''
        return {
            'ref_id': self.ref_id,
            'last_name': self.last_name.upper(),
            'first_name': self.first_name,
            'first_name_short': self.first_name.upper()[0],
            'gender': self.gender.upper()[0],
            'age': self.age(),
            'months': self.age(),
            'guardian': self.guardian,
            'location': self.location,
            'status': self.status}

    def years_months(self):
        now = datetime.now().date()
        return (now.year - self.dob.year, now.month - self.dob.month)

    def date_registered(self):
        '''Date case was registered '''
        return self.created_at.strftime("%d.%m.%y")

    def provider_mobile(self):
        '''reporters mobile number'''
        return self.reporter.connection().identity

    def short_name(self):
        '''Case short name: should not easily identify who really
         the patient is'''
        return "%s %s." % (self.first_name, self.last_name[0])

    def short_dob(self):
        return self.dob.strftime("%d.%m.%y")

    def age(self):
        '''Get the age of the case in months

        return string age
        '''
        if self.dob is not None:
            delta = datetime.now().date() - self.dob
            # FIXME: i18n
            return str(int(delta.days / 30.4375)) + "m"

    def eligible_for_measles(self):
        '''Check if case is eligible for measles vaccination

        case should be between 9 and 60 months old

        return True - if case is eligible for measles vaccination
        return False - if case is not eligible for measles vaccination
        '''
        if self.dob is not None:
            delta = datetime.now().date() - self.dob
            months = int(delta.days / 30.4375)

            if months >= 9 and months <= 60:
                return True
            return False

    @classmethod
    def list_e_4_measles(cls, reporter):
        '''List cases that ere eligible for measles vaccination'''
        ninem = date.today() - timedelta(int(30.4375 * 9))
        sixtym = date.today() - timedelta(int(30.4375 * 60))

        try:
            return cls.objects.filter(reporter=reporter, \
                                      dob__lte=ninem, dob__gte=sixtym)
        except models.ObjectDoesNotExist:
            return None

    @classmethod
    def count_by_provider(cls, reporter, status=None, \
                          start_date=None, end_date=None):
        '''Count the number of cases that a reporter is in charge of

        reporter - reporter in charge of the cases
        status - STATUS_ACTIVE | STATUS_INACTIVE | STATUS_DEAD |
         None - is equivalent to only active cases

        return int - count
        '''
        try:
            if status is None:
                status = Case.STATUS_ACTIVE
            if start_date is not None or end_date is not None:
                return cls.objects.filter(reporter=reporter, status=status, \
                    created_at__lte=end_date, \
                    created_at__gte=start_date).count()
            return cls.objects.filter(reporter=reporter, status=status).count()
        except models.ObjectDoesNotExist:
            return None

    @classmethod
    def count_for_last_30_days(cls, reporter, start_date=None, end_date=None):
        '''Count new cases in the last 30 days from today

        reporter - specific reporter

        return int - count
        '''
        if start_date is None or end_date is None:
            thirty_days = timedelta(days=30)
            end_date = date.today()
            start_date = end_date - thirty_days
        try:
            return cls.objects.filter(reporter=reporter, \
                created_at__lte=end_date, \
                created_at__gte=start_date).count()
        except models.ObjectDoesNotExist:
            return None

    def set_status(self, state):
        '''change the status of a case

        state - the status to be applied - STATUS_ACTIVE, STATUS_INACTIVE,
             STATUS_DEAD
        '''
        states = dict([(k, v) for (k, v) in self.STATUS_CHOICES])
        rst = states.get(state, None)
        if rst is None:
            return None
        self.status = state
        return state

    @classmethod
    def update_overage_status(cls):
        '''Update status of over 60 months cases to inactive.'''
        sixtym = date.today() - timedelta(int(30.4375 * 60))

        try:
            cases = cls.objects.filter(dob__lte=sixtym, \
                                       status=Case.STATUS_ACTIVE)
            count = cases.count()
            for case in cases:
                case.set_status(Case.STATUS_INACTIVE)
                case.save()

            return count
        except models.ObjectDoesNotExist:
            return None


class CaseNote(models.Model):

    ''' Holds notes for Cases

        case - Case object
        created_by - reporter
        created_at - time created
        text - stores the note text
    '''

    case = models.ForeignKey(Case, related_name="notes", db_index=True)
    created_by = models.ForeignKey(Reporter, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    text = models.TextField()

    def save(self, *args):
        if not self.id:
            self.created_at = datetime.now()
        super(CaseNote, self).save(*args)

    class Meta:
        app_label = "childcount"
