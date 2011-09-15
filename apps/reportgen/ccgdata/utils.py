#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

from rapidsms.webui import settings

from reportgen.timeperiods import TwelveMonths
from reportgen.definitions.VitalEventsReport import ReportDefinition as \
                                                        VEsReportDefinition

from reportgen.ccgdata import CCGData


def update_header_vital_events_worksheet(ccgdata, key, wksht_id):
    if not isinstance(ccgdata, CCGData):
        raise Exception("ccgdata is not an instance of CCGData.")
    headers = ["Indicator"]
    # a time period creates the headers i.e Year Month e.g 2011 September
    last12months = TwelveMonths._twelvemonth_period(0)
    headers.extend([p.start.strftime("%Y %B") for p in \
                    last12months.sub_periods()])
    row = 1
    for i in range(1, headers.__len__() + 1):
        col = i
        ccgdata.cellsUpdateAction(key, wksht_id, row, col, headers[i - 1])


def default_vital_events_worksheet(ccgdata, key, wksht_id):
    if not isinstance(ccgdata, CCGData):
        raise Exception("ccgdata is not an instance of CCGData.")
    # headers
    update_header_vital_events_worksheet(ccgdata, key, wksht_id)
    # indicators
    indicators = [unicode(ind.short_name) for ind in \
                                            VEsReportDefinition._indicators]

    col = 1
    for i in range(1, indicators.__len__()):
        row = i + 1
        ccgdata.cellsUpdateAction(key, wksht_id, row, col, indicators[i - 1])


def update_vital_events_worksheet(ccgdata, key, wksht_id, data):
    if not isinstance(ccgdata, CCGData):
        raise Exception("ccgdata is not an instance of CCGData.")
    # headers
    update_header_vital_events_worksheet(ccgdata, key, wksht_id)
    # indicators

    for i in range(1, data.__len__() + 1):
        row = i + 1
        rowdata = data[i - 1]
        for col in range(1, rowdata.__len__() + 1):
            ccgdata.cellsUpdateAction(key, wksht_id, row, col, \
                str(rowdata[col - 1]))


def update_vital_events_report():
    conf = settings.RAPIDSMS_APPS["reportgen"]
    username = conf["gdata.username"]
    password = conf["gdata.password"]
    key = conf["gdata.key"]
    site= conf["site"]

    ccgdata = CCGData()

    try:
        ccgdata.login(username, password)
    except Exception:
        raise Exception("Error: Unable to login to google docs")
    else:
        wksht_id = ccgdata.createWorksheet(key, site)
        # default_vital_events_worksheet(ccgdata, key, wksht_id)

        last12months = TwelveMonths._twelvemonth_period(0)
        data = VEsReportDefinition.data_only(last12months)

        update_vital_events_worksheet(ccgdata, key, wksht_id, data)