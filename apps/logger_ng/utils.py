#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import urllib2
from urllib import urlencode

import rapidsms
from rapidsms.webui import settings

from logger_ng import config


def respond_to_msg(msg, text):
    '''
    Sends a message to a reporter using the ajax app.  This goes to
    ajax_POST_send_message in logger_ng app.py
    '''
    conf = settings.RAPIDSMS_APPS['ajax']
    slug = config.title.replace(' ', '-').lower()
    url = "http://%s:%s/%s/send_message" % (conf["host"], conf["port"], slug)

    data = {'msg_pk': msg.pk, \
            'text': text}
    req = urllib2.Request(url, urlencode(data))
    stream = urllib2.urlopen(req)
    stream.close()
