#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

from rapidsms.webui.utils import render_to_response
from django.utils.translation import gettext_lazy as _
from django.template import Template, Context

from childcount.models import Patient, CHW
from childcount.models.ccreports import TheCHWReport



def index(request):
    '''Index page '''
    template_name = "childcount/index.html"
    title = "ChildCount-2.0"
    nutrition = "%(atrisk)s/%(eligible)s" % {'atrisk': TheCHWReport.total_at_risk(), \
                           'eligible': TheCHWReport.total_muac_eligible()}
    return render_to_response(request, template_name, {
            "title": title, 'nutrition': nutrition})


def chw(request):
    '''Community Health Worker page '''
    report_title = CHW._meta.verbose_name
    rows = []
    columns, sub_columns = CHW.table_columns()

    reports = CHW.objects.filter(role__code='chw')
    i = 0
    for report in reports:
        patients = Patient.objects.filter(chw=report)
        num_patients = patients.count()
        num_under_5 = 0
        for person in patients:
            if person.age_in_days_weeks_months()[2] < 60:
                num_under_5 += 1
        i += 1
        row = {}
        row["cells"] = []
        row["cells"] = [{'value': \
                        Template(col['bit']).render(Context({'object': \
                            report}))} for col in columns]
        row["cells"][-2] = {"value": num_patients}
        row["cells"][-1] = {"value": num_under_5}

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
    print columns[1:]
    aocolumns_js = aocolumns_js[:-1]

    aggregate = False
    print columns
    print sub_columns
    print len(rows)
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
        return render_to_response(request, 'childcount/chw.html', context_dict)
    else:
        return render_to_response(request, 'childcount/chw.html', context_dict)


def patient(request):
    '''Patients page '''
    report_title = Patient._meta.verbose_name
    rows = []
    columns, sub_columns = Patient.table_columns()

    reports = Patient.objects.all()
    i = 0
    for report in reports:
        i += 1
        row = {}
        row["cells"] = []
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
    print columns[1:]
    aocolumns_js = aocolumns_js[:-1]

    aggregate = False
    print columns
    print sub_columns
    print len(rows)
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
        return render_to_response(\
                request, 'childcount/patient.html', context_dict)
    else:
        return render_to_response(\
                request, 'childcount/patient.html', context_dict)
