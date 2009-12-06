#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

'''ChildCount Logging models

EventLog - for events logging
SystemErrorLog - for exceptions logging
MessageLog - for sms message logging

'''

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User

from datetime import datetime, date

from reporters.models import Reporter

# since there's only ever going to be a limited number of message
# on a strict one to one basis, lets just define them here,
# pushing the full text or setting up another model would work too
messages = {
    "provider_registered": _("Provider registered, awaiting confirmation"),
    "patient_created": _("Patient created"),
    "muac_taken": _("MUAC taken for the patient"),
    "diarrhea_taken": _("DIARRHEA taken for the patient"),
    "diarrhea_fu_taken": _("DIARRHEA follow-up received for the patient"),
    "mrdt_taken": _("MRDT taken for the patient"),
    "diagnosis_taken": _("Diagnosis taken for the patient"),
    "user_logged_in": _("User logged into the user interface"),
    "confirmed_join": _("Provider confirmed"),
    "case_cancelled": _("Case was cancelled by the provider"),
    "case_transferred": _("Case was transferred to the current provider"),
    "note_added": _("Note added to the case by the provider")}


class MessageDoesNotExist(Exception):
    pass


class EventLog(models.Model):

    ''' This is a much more refined log, giving you nicer messages '''

    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType)
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    message = models.CharField(max_length=25, choices=tuple(messages.items()))
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "childcount"
        ordering = ("-created_at",)

    def get_absolute_url(self):
        return self.content_object.get_absolute_url()

    def __unicode__(self):
        return u"%(date)s - %(msg)s (%(type)s)" % {'date': self.created_at, \
                            'msg': self.message, 'type': self.content_type}


class SystemErrorLog(models.Model):

    ''' This is for exception errors '''

    message = models.CharField(max_length=500)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "childcount"
        ordering = ("-created_at",)

    def get_absolute_url(self):
        return self.content_object.get_absolute_url()

    def __unicode__(self):
        return u"%(date)s - %(msg)s (%(type)s)" % {'date': self.created_at, \
                            'msg': self.message, 'type': self.content_type}


def elog(source, message):
    "Logs error messages"
    ev = SystemErrorLog()
    ev.message = message
    ev.created_at = datetime.now()
    ev.save()


def log(source, message):
    '''Logs events'''
    if message in messages:
        raise MessageDoesNotExist("No message: %s exists, "\
                                  "please add to logs.py")
    if not source.id:
        print "* Cannot log until the object has been saved, id is None, %s"\
         % message
    ev = EventLog()
    ev.content_object = source
    ev.message = message
    ev.created_at = datetime.now()
    ev.save()


class MessageLog(models.Model):

    ''' This is the raw dirt message log, useful for some things '''

    mobile = models.CharField(max_length=255, db_index=True)
    sent_by = models.ForeignKey(Reporter, null=True)
    text = models.TextField(max_length=255)
    was_handled = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "childcount"
        ordering = ("-created_at",)

    def provider_number(self):
        '''reporters mobile phone number'''
        return self.reporter.conection().identity

    def sent_by_name(self):
        '''reporter's name'''
        try:
            return "%s %s" % (self.sent_by.first_name, self.sent_by.last_name)
        except:
            return "Unknown"

    def location(self):
        '''Reporter's Location'''
        return u"%s" % self.sent_by.location

    def save(self, *args):
        if not self.id:
            self.created_at = datetime.now()
        super(MessageLog, self).save(*args)

    @classmethod
    def count_by_provider(cls, reporter, duration_end=None, \
                          duration_start=None):
        '''Count of all messages received per reporter'''
        if reporter is None:
            return None
        try:
            if duration_start is None or duration_end is None:
                return cls.objects.filter(reporter=reporter).count()
            return cls.objects.filter(created_at__lte=duration_end, \
                        created_at__gte=duration_start).\
                        filter(sent_by=reporter).count()
        except models.ObjectDoesNotExist:
            return None

    @classmethod
    def count_processed_by_provider(cls, reporter, duration_end=None, \
                                    duration_start=None):
        '''Count of correctly formatted messages received per reporter'''
        if reporter is None:
            return None
        try:
            if duration_start is None or duration_end is None:
                return cls.objects.filter(reporter=reporter).count()
            return cls.objects.filter(created_at__lte=duration_end, \
                        created_at__gte=duration_start).\
                        filter(sent_by=reporter, was_handled=True).count()
        except models.ObjectDoesNotExist:
            return None

    @classmethod
    def count_refused_by_provider(cls, reporter, duration_end=None, \
                                  duration_start=None):
        '''Count of incorrectly formatted messages received per reporter'''
        if reporter is None:
            return None
        try:
            if duration_start is None or duration_end is None:
                return cls.objects.filter(reporter=reporter).count()
            return cls.objects.filter(created_at__lte=duration_end, \
                            created_at__gte=duration_start).\
                            filter(sent_by=reporter, was_handled=True).count()
        except models.ObjectDoesNotExist:
            return None

    @classmethod
    def days_since_last_activity(cls, reporter):
        '''Count of days since last activity/message was received'''
        today = date.today()
        logs = MessageLog.objects.order_by("created_at").\
            filter(created_at__lte=today, sent_by=reporter).reverse()
        if not logs:
            return ""
        return (today - logs[0].created_at.date()).days
