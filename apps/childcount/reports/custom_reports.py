#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

import os
import copy
import csv
import cProfile
from time import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY
from types import StringType

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.template import Template, Context
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import F
from django.db.models import Count

from cStringIO import StringIO

try:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import letter, landscape, A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate, PageBreak
    from reportlab.platypus import Table, TableStyle, NextPageTemplate
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
except ImportError:
    pass

from childcount.models import Clinic, CHW, Patient, FormGroup, CCReport
from childcount.models import Encounter
from childcount.models.reports import BedNetReport
from childcount.models.ccreports import TheCHWReport
from childcount.models.ccreports import ThePatient, OperationalReport
from childcount.models.ccreports import OperationalReport
from childcount.models.ccreports import ClinicReport
from childcount.models.ccreports import TheBHSurveyReport
from childcount.utils import RotatedParagraph

from libreport.pdfreport import PDFReport, p
from libreport.csvreport import CSVReport
from libreport.pdfreport import MultiColDocTemplate
from libreport.pdfreport import ScaledTable

import ccdoc 
from childcount.reports.utils import render_doc_to_response
from childcount.reports.utils import report_filename, REPORTS_DIR

from locations.models import Location

styles = getSampleStyleSheet()

styleN = styles['Normal']
styleH = styles['Heading1']
styleH3 = styles['Heading3']


def all_patient_list_pdf(request, rfilter=u'all', rformat="html"):
    report_title = ThePatient._meta.verbose_name
    rows = []
    if rfilter == 'underfive':
        reports = ThePatient.under_five()
    else:
        reports = ThePatient.objects.all().order_by('chw', 'household')

    columns, sub_columns = ThePatient.patients_summary_list()

    if rformat == 'pdf':
        for report in reports:
            rows.append([data for data in columns])
        rpt = PDFReport()
        rpt.setTitle(report_title)
        rpt.setFilename('_'.join(report_title.split()))
        rpt.setTableData(reports, columns, _("All Patients"))
        return rpt.render()
    else:
        i = 0
        for report in reports:
            i += 1
            row = {}
            row["cells"] = [{'value': \
                             Template(col['bit']).render(Context({'object': \
                                                report}))} for col in columns]
            if i == 100:
                row['complete'] = True
                rows.append(row)
                break
            rows.append(row)

        aocolumns_js = "{ \"sType\": \"html\" },"
        for col in columns[1:] + (sub_columns if sub_columns != None else []):
            if not 'colspan' in col:
                aocolumns_js += "{ \"asSorting\": [ \"desc\", \"asc\" ], " \
                                "\"bSearchable\": true },"
        aocolumns_js = aocolumns_js[:-1]

        aggregate = False
        context_dict = {'get_vars': request.META['QUERY_STRING'],
                        'columns': columns, 'sub_columns': sub_columns,
                        'rows': rows, 'report_title': report_title,
                        'aggregate': aggregate, 'aocolumns_js': aocolumns_js}

        if request.method == 'GET' and 'excel' in request.GET:
            '''response = HttpResponse(mimetype="application/vnd.ms-excel")
            filename = "%s %s.xls" % \
                       (report_title, datetime.now().strftime("%d%m%Y"))
            response['Content-Disposition'] = "attachment; " \
                                              "filename=\"%s\"" % filename
            from findug.utils import create_excel
            response.write(create_excel(context_dict))
            return response'''
            return render_to_response(request, 'childcount/patient.html', \
                                        context_dict)
        else:
            return render_to_response(request, 'childcount/patient.html', \
                                        context_dict)


def all_patient_list_per_chw_pdf(request):
    report_title = ThePatient._meta.verbose_name

    rpt = PDFReport()
    rpt.setTitle(report_title)
    rpt.setFilename('_'.join(report_title.split()))
    rpt.setRowsPerPage(42)

    columns, sub_columns = ThePatient.patients_summary_list()

    chws = TheCHWReport.objects.all()
    for chw in chws:
        rows = []
        reports = ThePatient.objects.filter(chw=chw).order_by('household')
        summary = u"Number of Children: %(num)s" % {'num': reports.count()}
        for report in reports:
            rows.append([data for data in columns])

        sub_title = u"%s %s" % (chw, summary)
        #rpt.setElements([p(summary)])
        rpt.setTableData(reports, columns, chw, hasCounter=True)
        rpt.setPageBreak()

    return rpt.render()


def under_five(request):
    report_title = ThePatient._meta.verbose_name

    rpt = PDFReport()
    rpt.setTitle(report_title)
    rpt.setFilename('_'.join(report_title.split()))
    rpt.setRowsPerPage(42)

    columns, sub_columns = ThePatient.underfive_summary_list()

    chws = [TheCHWReport.objects.all()[2]]
    for chw in chws:
        rows = []
        reports = ThePatient.under_five(chw)
        summary = u"Number of Children: %(num)s" % {'num': reports.count()}
        for report in reports:
            rows.append([data for data in columns])

        sub_title = u"%s %s" % (chw, summary)
        #rpt.setElements([p(summary)])
        rpt.setTableData(reports, columns, chw, hasCounter=True)
        rpt.setPageBreak()
    return rpt.render()


def gen_underfive_register_pdf(f, clinic, rformat):
    story = []
    filename = "underfive-%s.%s" % (clinic, rformat)
    clinic = Clinic.objects.get(code=clinic)
    chws = TheCHWReport.objects.filter(clinic=clinic)
    if not chws.count():
        story.append(Paragraph(_("No report for %s.") % clinic, styleN))
    for chw in chws:
        plist = ThePatient.under_five(chw).filter(status=Patient.STATUS_ACTIVE)

        tb = under_five_table(_(u"CHW: %(loc)s: %(chw)s") % \
                                {'loc': clinic, 'chw': chw}, plist)
        story.append(tb)
        story.append(PageBreak())
        # 108 is the number of rows per page, should probably put this in a
        # variable
        pcount = plist.count()
        if (((pcount/ 108) + 1) % 2) == 1 \
            and not (pcount / 108) * 108 == pcount:
            story.append(PageBreak())
    story.insert(0, PageBreak())
    story.insert(0, PageBreak())
    story.insert(0, NextPageTemplate("laterPages"))
    doc = MultiColDocTemplate(report_filename(filename), 2, pagesize=A4, \
                            topMargin=(0.5 * inch), showBoundary=0)
    doc.build(story)
    return HttpResponseRedirect( \
        '/static/childcount/' + REPORTS_DIR + '/' + filename)


def under_five_table(title, indata=None, boxes=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleH5 = copy.copy(styleH3)
    styleH5.fontSize = 8
    styleN.fontSize = 8
    styleN.spaceAfter = 0
    styleN.spaceBefore = 0
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT
    styleN4 = copy.copy(styleN2)
    styleN4.fontName = 'Times-Bold'

    cols, sub_columns = ThePatient.underfive_summary_list()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols)) * [''])
    cmd = [Paragraph(u"Generated at %s" % \
                    datetime.now().strftime('%Y-%d-%m %H:%M:%S'), styleN)]
    cmd.extend((len(cols)) * [''])
    data = [hdata, cmd]

    firstrow = [Paragraph(u"#", styleH5)]
    firstrow.extend([Paragraph(col['name'], styleH5) for col in cols])
    data.append(firstrow)

    rowHeights = [None, None, 0.2 * inch]
    colWidths = [0.5 * inch, 0.5 * inch, 2.0 * inch, 1.0 *inch]

    ts = [('SPAN', (0, 0), (len(cols), 0)), ('SPAN', (0, 1), (len(cols), 1)),
                            ('LINEABOVE', (0, 2), (len(cols), 2), 1, \
                            colors.black),
                            ('LINEBELOW', (0, 1), (len(cols), 1), 1, \
                            colors.black),
                            ('LINEBELOW', (0, 2), (len(cols), 2), 1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey)]
    if indata:
        counter = 0
        for row in indata:
            counter += 1
            ctx = Context({"object": row})
            values = [Paragraph("%s" % counter, styleN2)]
            values.extend([Paragraph(Template(cols[0]["bit"]).render(ctx),
                            styleN4)])
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN) for col in cols[1:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.2 * inch])
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=3)
    tb.setStyle(TableStyle(ts))
    return tb


def chw(request, rformat='html'):
    '''Community Health Worker page '''
    report_title = TheCHWReport._meta.verbose_name
    rows = []

    reports = TheCHWReport.objects.filter(role__code='chw')
    columns, sub_columns = TheCHWReport.summary()
    if rformat.lower() == 'pdf':
        rpt = PDFReport()
        rpt.setTitle(report_title)
        rpt.setFilename('_'.join(report_title.split()))

        for report in reports:
            rows.append([data for data in columns])

        rpt.setTableData(reports, columns, report_title)
        rpt.setPageBreak()

        return rpt.render()
    else:
        i = 0
        for report in reports:
            i += 1
            row = {}
            row["cells"] = [{'value': \
                             Template(col['bit']).render(Context({'object': \
                                                report}))} for col in columns]
            if i == 100:
                row['complete'] = True
                rows.append(row)
                break
            rows.append(row)

        aocolumns_js = "{ \"sType\": \"html\" },"
        for col in columns[1:] + (sub_columns if sub_columns != None else []):
            if not 'colspan' in col:
                aocolumns_js += "{ \"asSorting\": [ \"desc\", \"asc\" ], " \
                                "\"bSearchable\": true },"
        aocolumns_js = aocolumns_js[:-1]

        aggregate = False
        context_dict = {'get_vars': request.META['QUERY_STRING'],
                        'columns': columns, 'sub_columns': sub_columns,
                        'rows': rows, 'report_title': report_title,
                        'aggregate': aggregate, 'aocolumns_js': aocolumns_js}

        if request.method == 'GET' and 'excel' in request.GET:
            '''response = HttpResponse(mimetype="application/vnd.ms-excel")
            filename = "%s %s.xls" % \
                       (report_title, datetime.now().strftime("%d%m%Y"))
            response['Content-Disposition'] = "attachment; " \
                                              "filename=\"%s\"" % filename
            from findug.utils import create_excel
            response.write(create_excel(context_dict))
            return response'''
            return render_to_response(request, 'childcount/chw.html', \
                                        context_dict)
        else:
            return render_to_response(request, 'childcount/chw.html', \
                                            context_dict)

def gen_operationalreport():
    '''
    Generate OperationalReport and write it to file
    '''
    filename = report_filename('operationalreport.pdf')
    f = open(filename, 'w')
    styleNC = copy.copy(styleN)
    styleNC.alignment = TA_CENTER
    story = []
    clinics = Clinic.objects.filter(pk__in=CHW.objects.values('clinic')\
                                                    .distinct('clinic'))
    for clinic in clinics:
        if not TheCHWReport.objects.filter(clinic=clinic).count():
            continue
        tb = operationalreportable(clinic, TheCHWReport.objects.\
            filter(clinic=clinic))
        story.append(Paragraph('Generated at %s' % \
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), styleNC))
        story.append(tb)
        story.append(PageBreak())

    doc = SimpleDocTemplate(f, pagesize=landscape(A4), \
                            topMargin=(0 * inch), \
                            bottomMargin=(0 * inch))
    doc.build(story)

    f.close()


def operationalreportable(title, indata=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    opr = OperationalReport()
    cols = opr.get_columns()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata, ['', Paragraph('Household', styleH3), '', '', \
            Paragraph('Newborn', styleH3), '', '', \
            Paragraph('Under-5\'s', styleH3), '', \
            '', '', '', '', Paragraph('Pregnant', styleH3), '', '', \
            Paragraph('Follow-up', styleH3), '', \
            Paragraph('SMS', styleH3), ''], \
            ['', Paragraph('A1', styleH3), Paragraph('A2', styleH3), \
            Paragraph('A3', styleH3), Paragraph('B1', styleH3), \
            Paragraph('B2', styleH3), Paragraph('B3', styleH3), \
            Paragraph('C1', styleH3), Paragraph('C2', styleH3), \
            Paragraph('C3', styleH3), Paragraph('C4',  styleH3), \
            Paragraph('C5', styleH3), Paragraph('C6', styleH3), \
            Paragraph('D1', styleH3), Paragraph('D2', styleH3), \
            Paragraph('D3', styleH3), Paragraph('E1', styleH3), \
            Paragraph('E2', styleH3), Paragraph('F1', styleH3), \
            Paragraph('F2', styleH3)]]

    thirdrow = [Paragraph(cols[0]['name'], styleH3)]
    thirdrow.extend([RotatedParagraph(Paragraph(col['name'], styleN), \
                                2.3 * inch, 0.25 * inch) for col in cols[1:]])
    data.append(thirdrow)

    fourthrow = [Paragraph('Target:', styleH3)]
    fourthrow.extend([Paragraph(item, styleN) for item in ['-', '-', '100', \
                        '-', '100', '100', '-', '-', '-', '-', '100', '-', \
                        '-', '-', '100', '100', '&lt;=2', '0', '-']])
    data.append(fourthrow)

    fifthrow = [Paragraph('<u>List of CHWs</u>', styleH3)]
    fifthrow.extend([Paragraph(item, styleN) for item in [''] * 19])
    data.append(fifthrow)

    rowHeights = [None, None, None, 2.3 * inch, 0.25 * inch, 0.25 * inch]
    colWidths = [1.5 * inch]
    colWidths.extend((len(cols) - 1) * [0.5 * inch])

    if indata:
        for row in indata:
            ctx = Context({"object": row})
            values = [Paragraph(Template(cols[0]["bit"]).render(ctx), \
                                styleN)]
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN3) for col in cols[1:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.25 * inch])
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=6)
    tb.setStyle(TableStyle([('SPAN', (0, 0), (19, 0)),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey), \
                            ('BOX', (1, 1), (3, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (1, 1), (3, 1)), \
                            ('SPAN', (4, 1), (6, 1)), \
                            ('BOX', (7, 1), (12, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (7, 1), (12, 1)), \
                            ('SPAN', (13, 1), (15, 1)), \
                            ('BOX', (16, 1), (17, -1), 5, \
                            colors.lightgrey),\
                            ('SPAN', (16, 1), (17, 1)), \
                            ('SPAN', (-2, 1), (-1, 1)), \
                ]))
    return tb

def gen_registerlist():
    clinics = Clinic.objects.all()
    for c in clinics:
        for active in ['','-active']:
            filename = report_filename("registerlist-%s%s.pdf" % (c.code, active))
            f = open(filename, 'w')

            gen_patient_register_pdf(f, c, (active == '-active'))
            f.close()

def gen_patient_register_pdf(f, clinic, active=False):
    story = []
    chws = TheCHWReport.objects.filter(clinic=clinic)
    if not chws.count():
        story.append(Paragraph(_("No report for %s.") % clinic, styleN))
    for chw in chws:
        households = chw.households().order_by('location__code','last_name')
        if not households:
            continue
        patients = []
        boxes = []
        last_loc = None
        for household in households:
            # Put blank line between cells
            if last_loc != None and last_loc != household.location.code:
                patients.append(ThePatient())

            trow = len(patients)
            patients.append(household)
            hs = ThePatient.objects.filter(household=household)\
                            .exclude(health_id=household.health_id)\
                            .order_by('last_name')
            if active:
                hs = hs.filter(status=ThePatient.STATUS_ACTIVE)
            patients.extend(hs)

            last_loc = household.location.code
            brow = len(patients) - 1
            boxes.append({"top": trow, "bottom": brow})

        '''Sauri specific start: include default household id generated
        when migrating patients from old core ChildCount to the new core of
        ChildCount+'''
        if ThePatient.objects.filter(health_id='XXXXX'):
            #default_household -> dh
            dh = ThePatient.objects.get(health_id='XXXXX')
            patients.append(dh)
            hs = ThePatient.objects.filter(household=dh, \
                                            chw=chw)\
                                    .exclude(health_id=dh.health_id)
            if active:
                hs = hs.filter(status=ThePatient.STATUS_ACTIVE)
            patients.extend(hs)
            brow = len(patients) - 1
            boxes.append({"top": trow, "bottom": brow})
        #End Sauri specific

        tb = thepatientregister(_(u"CHW: %(loc)s: %(chw)s") % \
                                {'loc': clinic, 'chw': chw}, \
                                patients, boxes)
        story.append(tb)
        story.append(PageBreak())
        # 108 is the number of rows per page, should probably put this in a
        # variable
        if (((len(patients) / 108) + 1) % 2) == 1 \
            and not (len(patients) / 108) * 108 == len(patients):
            story.append(PageBreak())
    story.insert(0, PageBreak())
    story.insert(0, PageBreak())
    story.insert(0, NextPageTemplate("laterPages"))
    doc = MultiColDocTemplate(f, 2, pagesize=A4, \
                            topMargin=(0.5 * inch), showBoundary=0)
    doc.build(story)
    return f


def thepatientregister(title, indata=None, boxes=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleH5 = copy.copy(styleH3)
    styleH5.fontSize = 8
    styleN.fontSize = 8
    styleN.spaceAfter = 0
    styleN.spaceBefore = 0
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    rpt = ThePatient()
    cols = rpt.patient_register_columns()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata]

    firstrow = [Paragraph(cols[0]['name'], styleH5)]
    firstrow.extend([Paragraph(col['name'], styleH5) for col in cols[1:]])
    data.append(firstrow)

    rowHeights = [None, 0.2 * inch]
    # Loc, HID, Name
    colWidths = [0.5 * inch, 0.5 * inch, 1.3 * inch]
    colWidths.extend((len(cols) - 3) * [0.4 * inch])

    ts = [('SPAN', (0, 0), (len(cols) - 1, 0)),
                            ('LINEABOVE', (0, 1), (len(cols) - 1, 1), 1, \
                            colors.black),
                            ('LINEBELOW', (0, 1), (len(cols) - 1, 1), 1, \
                            colors.black),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey)]
    if indata:
        for row in indata:
            ctx = Context({"object": row})
            values = [Paragraph(Template(cols[0]["bit"]).render(ctx), \
                                styleN)]
            values.extend([Paragraph(Template(cols[1]["bit"]).render(ctx), \
                                styleN)])
            values.extend([Paragraph(Template(cols[2]["bit"]).render(ctx), \
                                styleN)])
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN2) for col in cols[3:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.2 * inch])

        tscount = 0
        for box in boxes:
            if tscount % 2:
                ts.append((('BOX', (0, box['top'] + 2), \
                        (-1, box['bottom'] + 2), 0.5, colors.black)))
            else:
                ts.append((('BOX', (0, box['top'] + 2), \
                        (-1, box['bottom'] + 2), 0.5, colors.black)))
            ts.append((('BACKGROUND', (0, box['top'] + 2), \
                        (2, box['top'] + 2), colors.lightgrey)))
            tscount += 1
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=2)
    tb.setStyle(TableStyle(ts))
    return tb


def surveyreport(request, rformat):
    filename = 'surveyreport.pdf'
    story = []
    fn = os.path.abspath(os.path.join(os.path.dirname(__file__), \
                    './rpts/%s' % filename))
    if not os.path.isfile(fn):
        return HttpResponse(_(u"No Report Generated yet"))
    else:
        f = open(fn, 'r')
        pdf = f.read()
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    response.write(pdf)
    return response


def a_surveyreport(request, rformat="html"):
    doc = ccdoc.Document(u'Household Healthy Survey Report')
    today = datetime.today()
    locations = Location.objects.filter(pk__in=CHW.objects.values('location')\
                                                    .distinct('location'))
    headings = TheBHSurveyReport.healthy_survey_columns()
    for location in locations:
        brpts = BedNetReport.objects.filter(encounter__chw__location=location)
        if not brpts.count():
            continue
        t = ccdoc.Table(headings.__len__())
        t.add_header_row([
                    ccdoc.Text(c['name']) for c in headings])
        for row in TheBHSurveyReport.objects.filter(location=location):
            ctx = Context({"object": row})
            row = []
            for cell in headings:
                cellItem = Template(cell['bit']).render(ctx)
                if cellItem.isdigit():
                    cellItem = int(cellItem)
                cellItem = ccdoc.Text(cellItem)
                row.append(cellItem)
            t.add_row(row)
        doc.add_element(ccdoc.Section(u"%s" % location))
        doc.add_element(t)
    return render_doc_to_response(request, rformat, doc, 'hhsurveyrpt')


def gen_surveyreport():
    '''
    Generate the healthy survey report.
    '''
    filename = report_filename('surveyreport.pdf')
    f = open(filename, 'w')
    styleNC = copy.copy(styleN)
    styleNC.alignment = TA_CENTER
    story = []

    clinics = Clinic.objects.all()
    for clinic in clinics:
        if not TheBHSurveyReport.objects.filter(clinic=clinic).count():
            continue
        tb = surveyreportable(clinic, TheBHSurveyReport.objects.\
            filter(clinic=clinic))
        story.append(Paragraph('Generated at %s' % \
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), styleNC))
        story.append(tb)
        story.append(PageBreak())

    doc = SimpleDocTemplate(f, pagesize=landscape(A4), \
                            topMargin=(0 * inch), \
                            bottomMargin=(0 * inch))
    doc.build(story)

    f.close()


def surveyreportable(title, indata=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    cols = TheBHSurveyReport.healthy_survey_columns()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata]

    thirdrow = [Paragraph(cols[0]['name'], styleH3)]
    thirdrow.extend([RotatedParagraph(Paragraph(col['name'], styleN), \
                                2.3 * inch, 0.25 * inch) for col in cols[1:]])
    data.append(thirdrow)

    rowHeights = [None, 2.3 * inch]
    colWidths = [3.0 * inch]
    colWidths.extend((len(cols) - 1) * [0.5 * inch])

    if indata:
        for row in indata:
            ctx = Context({"object": row})
            values = [Paragraph(Template(cols[0]["bit"]).render(ctx), \
                                styleN)]
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN3) for col in cols[1:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.25 * inch])
    tb = Table(data, colWidths=colWidths, rowHeights=rowHeights, repeatRows=6)
    tb.setStyle(TableStyle([('SPAN', (0, 0), (colWidths.__len__() - 1, 0)),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),
                            ('BOX', (3, 1), (8, -1), 5, \
                            colors.lightgrey),
                            ('BOX', (8, 1), (9, -1), 5, \
                            colors.lightgrey),
                            ('BOX', (9, 1), (10, -1), 5, \
                            colors.lightgrey)]))
    return tb


def clinic_monthly_summary_csv(request):
    '''
    Monthly clinic summary
    '''
    filename = "monthly_summary.csv"
    start_date = datetime(year=2010, month=1, day=1)
    current_date = datetime.today()
    buffer = StringIO()
    dw = csv.DictWriter(buffer, ['clinic', 'month', 'rdt', 'positive_rdt', \
                                        'nutrition', 'malnutrition'])
    for clinic in ClinicReport.objects.all():
        i = 1
        header = {'clinic': _(u"Clinic/Health Facility"), \
                    'month': _(u"Month"), \
                    'rdt': _(u"# of Fever Report(RDT)"), \
                    'positive_rdt': _(u"# Positive Fever Report"), \
                    'nutrition': _(u"# Nutrition Report"), \
                    'malnutrition': _(u"# Malnourished")}
        dw.writerow(header)
        while i <= 12:
            data = clinic.monthly_summary(i, start_date.year)
            dw.writerow(data)
            i += 1
    rpt = buffer.getvalue()
    buffer.close()
    response = HttpResponse(mimetype='application/csv')
    response['Cache-Control'] = ""
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    response.write(rpt)
    return response

def gen_all_household_surveyreports():
    clinics = Clinic.objects.all()
    for clinic in clinics:
        filename = report_filename('hhsurvey-%s.pdf' % clinic.code)
        f = open(filename, 'w')
        gen_household_surveyreport(f, clinic)
        f.close()

def gen_household_surveyreport(filename, location=None):
    story = []
    if StringType == type(filename):
        filename = StringIO()
    chws = None
    if location:
        try:
            chws = TheCHWReport.objects.filter(clinic=location)
        except TheCHWReport.DoesNotExist:
            raise BadValue(_(u"Unknown Location: %(location)s specified." % \
                                {'location': location}))
    if chws is None and  TheCHWReport.objects.all().count():
        chws = TheCHWReport.objects.all()

    for chw in chws:
        if not ThePatient.objects.filter(chw=chw, \
                            health_id=F('household__health_id')).count():
            continue
        patients = ThePatient.objects.filter(\
                health_id=F('household__health_id'), chw=chw).\
                order_by('location')
        tb = household_surveyreportable(_(u"Bednet Report - %(loc)s: %(chw)s" \
                                        % {'chw': chw, 'loc': chw.clinic}), \
                                        patients)
        story.append(tb)
        story.append(PageBreak())

        # 40 is the number of rows per page, should probably put this in a
        # variable
        if (((len(patients) / 47) + 1) % 2) == 1 \
            and not (len(patients) / 47) * 47 == len(patients):
            story.append(PageBreak())

    doc = SimpleDocTemplate(filename, pagesize=(8.5 * inch, 13.5 * inch), \
                            topMargin=(0 * inch), \
                            bottomMargin=(0 * inch), showBoundary=0)
    doc.build(story)


def household_surveyreport(location=None):
    '''
    Generate the healthy survey report.
    '''
    filename = report_filename('HouseholdSurveyReport.pdf')
    f = open(filename, 'w')

    story = []

    if TheCHWReport.objects.all().count():
        for chw in TheCHWReport.objects.all():
            if not ThePatient.objects.filter(\
                                health_id=F('household__health_id')).count():
                continue
            tb = household_surveyreportable(chw, ThePatient.objects.filter(\
                    health_id=F('household__health_id'), chw=chw).\
                    order_by('location'))
            story.append(tb)
            story.append(PageBreak())

    doc = SimpleDocTemplate(f, pagesize=landscape(A4), \
                            topMargin=(0 * inch), \
                            bottomMargin=(0 * inch))
    doc.build(story)

    f.close()


def household_surveyreportable(title, indata=None):
    styleH3.fontName = 'Times-Bold'
    styleH3.alignment = TA_CENTER
    styleN2 = copy.copy(styleN)
    styleN2.alignment = TA_CENTER
    styleN3 = copy.copy(styleN)
    styleN3.alignment = TA_RIGHT

    cols, subcol = ThePatient.bednet_summary_minimal()

    hdata = [Paragraph('%s' % title, styleH3)]
    hdata.extend((len(cols) - 1) * [''])
    data = [hdata]

    thirdrow = ['#', RotatedParagraph(Paragraph(cols[0]['name'], styleH3), \
                                1.3 * inch, 0.25 * inch)]
    thirdrow.extend([Paragraph(cols[1]['name'], styleN)])
    thirdrow.extend([Paragraph(cols[2]['name'], styleN)])
    thirdrow.extend([RotatedParagraph(Paragraph(col['name'], styleN), \
                                1.3 * inch, 0.25 * inch) for col in cols[3:]])
    data.append(thirdrow)

    rowHeights = [None, 1.3 * inch]
    colWidths = [0.3 * inch, 0.6 * inch, 0.8 * inch, 1.5 * inch]
    colWidths.extend((len(cols) - 3) * [0.5 * inch])

    if indata:
        c = 0
        for row in indata:
            c = c + 1
            ctx = Context({"object": row})
            values = ["%d" % c, \
                        Paragraph(Template(cols[0]["bit"]).render(ctx), \
                        styleN)]
            values.extend([Paragraph(Template(col["bit"]).render(ctx), \
                                styleN3) for col in cols[1:]])
            data.append(values)
        rowHeights.extend(len(indata) * [0.25 * inch])
    tb = ScaledTable(data, colWidths=colWidths, rowHeights=rowHeights, \
            repeatRows=2)
    tb.setStyle(TableStyle([('SPAN', (0, 0), (colWidths.__len__() - 1, 0)),
                            ('INNERGRID', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),\
                            ('BOX', (0, 0), (-1, -1), 0.1, \
                            colors.lightgrey),
                            ('BOX', (4, 1), (8, -1), 5, \
                            colors.lightgrey),
                            ('BOX', (9, 1), (12, -1), 5, \
                            colors.lightgrey),
                            ('BOX', (13, 1), (14, -1), 5, \
                            colors.lightgrey),
                            ('BOX', (15, 1), (16, -1), 5, \
                            colors.lightgrey)]))
    return tb


def num_under_five_per_clinic(request, rformat="html"):
    '''Number of Under Five Per Clinic'''
    doc = ccdoc.Document(unicode(_(u"Number of Under Five Per Clinic")))
    today = datetime.today()
    max_dob = today + relativedelta(months=-59)
    ps = Patient.objects.filter(dob__gt=max_dob, status=Patient.STATUS_ACTIVE)
    ps = ps.exclude(chw__clinic=None)
    ps = ps.values('chw__clinic__name', 'gender')
    ps = ps.annotate(Count('id'), Count('gender'))
    data = {}
    for p in ps:
        if data.has_key(p['chw__clinic__name']):
            data[p['chw__clinic__name']].update({p['gender']:
                                                            p['id__count']})
        else:
            data.update({p['chw__clinic__name']: {p['gender']:
                                                        p['id__count']}})
    t = ccdoc.Table(4)
    t.add_header_row([
        ccdoc.Text(unicode(_(u"CLinic"))),
        ccdoc.Text(unicode(_(u"Number of Under Five"))),
        ccdoc.Text(unicode(_(u"Female"))),
        ccdoc.Text(unicode(_(u"Male")))])
    for row in data:
        if not data[row].has_key(Patient.GENDER_FEMALE):
            data[row][Patient.GENDER_FEMALE] = 0
        if not data[row].has_key(Patient.GENDER_MALE):
            data[row][Patient.GENDER_MALE] = 0
        total = data[row][Patient.GENDER_FEMALE] + \
                                    data[row][Patient.GENDER_MALE]
        t.add_row([
            ccdoc.Text(unicode(row)),
            ccdoc.Text(unicode(total)),
            ccdoc.Text(unicode(data[row][Patient.GENDER_FEMALE])),
            ccdoc.Text(unicode(data[row][Patient.GENDER_MALE]))])
    doc.add_element(t)

    return render_doc_to_response(request, rformat, doc,
                                    'num-under-five-per-clinic')


def ccforms_summary(request, rformat="html"):
    '''CCForms summary'''
    doc = ccdoc.Document(unicode(_(u"ChildCount Forms Summary")))
    fEnc = Encounter.objects.all().order_by('encounter_date')[0].encounter_date
    dtstart = datetime(fEnc.year, fEnc.month, 1)
    period = list(rrule(MONTHLY, dtstart=dtstart, until=datetime.today()))
    period.reverse()
    t = ccdoc.Table(2 + period.__len__())
    months = [ccdoc.Text(unicode(dt.strftime('%B, %Y'))) for dt in period]
    headers = [ccdoc.Text(unicode(_(u"Name"))),
                ccdoc.Text(unicode(_(u"Total")))]
    headers.extend(months)
    t.add_header_row(headers)
    data = {}
    for dt in period:
        recs = FormGroup.forms_summary(dt)
        for rec in recs:
            if not data.has_key(rec['name']):
                data[rec['name']] = []
            data[rec['name']].append(rec['count'])
    for row in FormGroup.forms_summary():
        items = [ccdoc.Text(unicode(row['name'])),
                    ccdoc.Text(unicode(row['count']))]
        items.extend([ccdoc.Text(unicode(i)) for i in data[row['name']]])
        t.add_row(items)
    doc.add_element(t)

    return render_doc_to_response(request, rformat, doc, 'ccforms-summary')


def ccreports_summary(request, rformat="html"):
    '''CCReport summary'''
    doc = ccdoc.Document(unicode(_(u"ChildCount Reports Summary")))
    fEnc = Encounter.objects.all().order_by('encounter_date')[0].encounter_date
    dtstart = datetime(fEnc.year, fEnc.month, 1)
    period = list(rrule(MONTHLY, dtstart=dtstart, until=datetime.today()))
    period.reverse()
    t = ccdoc.Table(2 + period.__len__())
    months = [ccdoc.Text(unicode(dt.strftime('%B, %Y'))) for dt in period]
    headers = [ccdoc.Text(unicode(_(u"Name"))),
                ccdoc.Text(unicode(_(u"Total")))]
    headers.extend(months)
    t.add_header_row(headers)
    for row in CCReport.__subclasses__():
        items = [ccdoc.Text(unicode(row._meta.verbose_name)),
                    ccdoc.Text(unicode(row.objects.filter().count()))]
        for dt in period:
            items.append(ccdoc.Text(unicode(row.objects.filter(\
                encounter__encounter_date__year=dt.year,
                encounter__encounter_date__month=dt.month).count())))
        t.add_row(items)
    doc.add_element(t)

    return render_doc_to_response(request, rformat, doc, 'ccreports-summary')
