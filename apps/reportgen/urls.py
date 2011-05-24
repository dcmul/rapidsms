#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8

import os

from django.conf.urls.defaults import include, patterns, url
from django.contrib import admin
import webapp

import reportgen.views

urlpatterns = patterns('',
    (r'^reportgen/$', reportgen.views.index),
    (r'^reportgen/ajax_status/$', reportgen.views.ajax_status),
    (r'^reportgen/nightly/$', 'reportgen-nightly', reportgen.views.nightly),
    (r'^reportgen/ondemand/$', reportgen.views.ondemand),
    (r'^reportgen/ondemand/delete/(?P<pk>\d+)$', reportgen.views.delete),
    url(r'^static/reportgen/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': '%s/static' % os.path.dirname(__file__),
                'show_indexes': False}),
)
