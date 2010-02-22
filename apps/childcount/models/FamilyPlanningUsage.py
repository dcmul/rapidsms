#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

from django.db import models
from django.utils.translation import ugettext as _


class FamilyPlanningUsage(models.Model):

    class Meta:
        app_label = 'childcount'
        verbose_name = _(u"Family Planning Usage")
        verbose_name_plural = _(u"Family Planning Usages")


    fp_report = models.ForeignKey('FamilyPlanningReport', \
                                   verbose_name=_(u"Family planning report"))
    method = models.ForeignKey('CodedItem', verbose_name=_(u"Method"))
    count = models.PositiveSmallIntegerField(_(u"Count"))
