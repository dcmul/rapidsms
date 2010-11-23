import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta

from django.utils.translation import gettext_lazy as _
from django.db.models import Count
from django.utils import simplejson
from django.http import HttpResponse

from locations.models import Location

from ccdoc import Document, Section, Table, Paragraph, Text

from childcount.models import PolioCampaignReport, Patient
from childcount.reports.utils import render_doc_to_response


def polio_summary(request, rformat="html"):
    doc = Document(unicode(_(u"Polio Campaign Summary Report")))
    today = datetime.today()
    dob = datetime.today() + relativedelta(months=-59)
    underfive = Patient.objects.filter(dob__gte=dob,
                                status=Patient.STATUS_ACTIVE)
    rpts = PolioCampaignReport.objects.filter()
    total = rpts.count()
    percentage = round((total / float(underfive.count())) * 100, 2)
    resp = _(u"%(percentage)s%% coverage, Total Reports: %(total)s. " % \
            {'total': total, 'percentage': percentage})
    rpts = rpts.values('chw__location__name', 'chw__location')
    rpts = rpts.annotate(Count('chw'))
    tail = [
            Text(unicode("Total")),
            Text(unicode(total)),
            Text(unicode(underfive.count())),
            Text(unicode("%s%%" % percentage))]
    t = Table(4)
    t.add_header_row([
        Text(unicode(_(u"Sub Location"))),
        Text(unicode(_(u"Number of Polio Vaccination"))),
        Text(unicode(_(u"# Target"))),
        Text(unicode(_(u"Percentage (%)")))])
    for row in rpts:
        uf = underfive.filter(chw__location__pk=row['chw__location'])
        percentage = round((row['chw__count'] / float(uf.count())) * 100, 2)
        t.add_row([
            Text(unicode(row['chw__location__name'])),
            Text(unicode(row['chw__count'])),
            Text(unicode(uf.count())),
            Text(unicode("%s%%" % percentage))])
    t.add_row(tail)
    doc.add_element(t)

    return render_doc_to_response(request, rformat, doc, 'polio-summary')


def polio_summary_by_location(request, rformat="html"):
    doc = Document(unicode(_(u"Polio Campaign Summary Report")))
    today = datetime.today()
    dob = datetime.today() + relativedelta(months=-59)
    underfive = Patient.objects.filter(dob__gte=dob,
                                status=Patient.STATUS_ACTIVE)
    rpts = PolioCampaignReport.objects.filter()
    locations = Location.objects.filter(type__name="Sub Location")
    for location in locations:
        loc_underfive = underfive.filter(chw__location=location)
        loc_rpts = rpts.filter(chw__location=location)
        total = loc_rpts.count()
        percentage = round((total / float(loc_underfive.count())) * 100, 2)
        resp = _(u"%(percentage)s%% coverage, Total Reports: %(total)s. " % \
                {'total': total, 'percentage': percentage})
        loc_rpts = loc_rpts.values('chw__first_name',
                                    'chw__last_name',
                                    'chw')
        loc_rpts = loc_rpts.annotate(Count('chw'))
        tail = [
                Text(unicode("Total")),
                Text(unicode(total)),
                Text(unicode(loc_underfive.count())),
                Text(unicode("%s%%" % percentage))]
        t = Table(4)
        t.add_header_row([
            Text(unicode(_(u"Name"))),
            Text(unicode(_(u"Number of Polio Vaccination"))),
            Text(unicode(_(u"# Target"))),
            Text(unicode(_(u"Percentage (%)")))])
        for row in loc_rpts:
            uf = loc_underfive.filter(chw__pk=row['chw'])
            try:
                percentage = round((row['chw__count'] / float(uf.count())) * \
                                                                        100, 2)
            except ZeroDivisionError:
                percentage = 0
            t.add_row([
                Text(unicode("%s %s" % (row['chw__first_name'],
                                        row['chw__last_name']))),
                Text(unicode(row['chw__count'])),
                Text(unicode(uf.count())),
                Text(unicode("%s%%" % percentage))])
        t.add_row(tail)
        doc.add_element(Section("%s" % location))
        doc.add_element(t)

    return render_doc_to_response(request, rformat, doc,
                                    'polio-summary-by-location')