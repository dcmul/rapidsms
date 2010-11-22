#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

import os

from django.conf.urls.defaults import include, patterns, url
from django.contrib import admin
import webapp

from childcount import views
from childcount.reports import statistics
from childcount.reports import operational
from childcount.reports import pmtct
from childcount.reports import polio
from childcount.reports import performance
from childcount.reports import custom_reports as reports

admin.autodiscover()

# an issue between Django version 1.0 and later?
# see http://code.djangoproject.com/ticket/10050
try:
    admin_urls = (r'^admin/', include(admin.site.urls))
except AttributeError:
    # Django 1.0 admin site
    admin_urls = (r'^admin/(.*)', admin.site.root)

urlpatterns = patterns('',
    admin_urls,

    # webapp URLS
    url(r'^accounts/login/$', "webapp.views.login", \
                     {'template_name': 'childcount/login.html'}, name='login'),
    url(r'^accounts/logout/$', "webapp.views.logout", \
                {'template_name': 'childcount/loggedout.html'}, name='logout'),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url('^static/webapp/(?P<path>.*)$', 'django.views.static.serve', \
        {'document_root': '%s/static' % os.path.dirname(webapp.__file__)}),

    url(r'^$', views.index, name='dashboard'),
    url(r'^childcount/?$', views.index, name='cc-dashboard'),
    url(r'^childcount/patients/?$', views.patient, name='cc-patients'),
    url(r'^childcount/patients/edit/((?P<healthid>[A-Z0-9]+)/)?$',
        views.edit_patient, name='cc-edit_patient'),
    #url(r'^childcount/patients/autocomplete/$',
    #    views.autocomplete),
    url(r'^childcount/patients/(?P<page>\d+)/?$', views.patient),
    url(r'^childcount/bednet/?$', views.bednet_summary),
    url(r'^childcount/patients/(?P<rfilter>[a-z]+)/(?P<rformat>[a-z]+)?$', \
        reports.all_patient_list_pdf),
    url(r'^childcount/patients_per_chw/pdf/?$', \
                                    reports.all_patient_list_per_chw_pdf),
    url(r'^childcount/chw/?$', views.chw),
    url(r'^childcount/chws/(?P<rformat>[a-z]*)$', reports.chw),
    url(r'^childcount/under_five', reports.under_five),
    url(r'^childcount/reports/underfive-(?P<clinic>[a-z]*).(?P<rformat>[a-z]*)$', reports.gen_underfive_register_pdf),
    url(r'^childcount/monthly-summary', reports.clinic_monthly_summary_csv),

    url(r'^childcount/reports/form_a_entered.(?P<rformat>[a-z]*)$',
        statistics.form_a_entered),
    url(r'^childcount/reports/form_b_entered.(?P<rformat>[a-z]*)$',
        statistics.form_b_entered),
    url(r'^childcount/reports/form_c_entered.(?P<rformat>[a-z]*)$',
        statistics.form_c_entered),
    url(r'^childcount/reports/operational_report.(?P<rformat>[a-z]*)$',
        operational.operational_report),
    url(r'^childcount/reports/encounters_per_day.(?P<rformat>[a-z]*)$', 
        statistics.encounters_per_day),

    url(r'^childcount/add_chw/?$', views.add_chw, name='cc-add_chw'),
    url(r'^childcount/list_chw/?$', views.list_chw, name='cc-list_chw'),

    url(r'^childcount/dataentry/?$', views.dataentry, name='cc-dataentry'),
    url(r'^childcount/dataentry/form/(?P<formid>[a-zA-Z0-9\-\_\.]*)/?$', \
                        views.form, name='form'),
    url(r'^childcount/site_summary/(?P<report>[a-z_]*)/(?P<format>[a-z]*)$', \
        views.site_summary),
    # PMTCT links
    url(r'^childcount/reports/pmtct-defaulters/(?P<rformat>[a-z]*)$', 
        pmtct.defaulters),
    url(r'^childcount/reports/pmtct-appointments/(?P<rformat>[a-z]*)$', 
        pmtct.appointments),
    url(r'^childcount/reports/pmtct-apts-aggregate/(?P<rformat>[a-z]*)$', 
        pmtct.appointments_aggregates),
    url(r'^childcount/reports/pmtct-apts-by-clinic/(?P<rformat>[a-z]*)$', 
        pmtct.appointments_by_clinic),
    url(r'^childcount/reports/pmtct-apts-error/(?P<rformat>[a-z]*)$', 
        pmtct.appointments_error_report),
    url(r'^childcount/reports/pmtct-deliveries/(?P<rformat>[a-z]*)$', 
        pmtct.upcoming_deliveries),
    url(r'^childcount/reports/pmtct-newregs/(?P<rformat>[a-z]*)$', 
        pmtct.new_registrations),
    url(r'^childcount/reports/pmtct-mothers-onfollowup/(?P<rformat>[a-z]*)$', 
        pmtct.active_mothers),
    url(r'^childcount/reports/pmtct-stats/(?P<rformat>[a-z]*)$', 
        pmtct.statistics),
    # survey rpts
    url(r'^childcount/reports/hhsurveyrpt.(?P<rformat>[a-z]*)$', 
        reports.a_surveyreport),
    url(r'^childcount/reports/performance.pdf$', 
        performance.chw_performance),
    url(r'^childcount/reports/num-under-five-per-clinic.(?P<rformat>[a-z]*)$', 
        reports.num_under_five_per_clinic),
    url(r'^childcount/reports/polio-summary.(?P<rformat>[a-z]*)$', 
        polio.polio_summary),
)
