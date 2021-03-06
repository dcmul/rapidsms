#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: katembu

from django.utils.translation import ugettext as _
from datetime import date, datetime

from childcount.forms import CCForm
from childcount.models import Encounter
from childcount.models.reports import LabReport, LabResultsReport

from childcount.models import LabTest
from childcount.models import LabTestResults

from childcount.exceptions import BadValue
from childcount.exceptions import ParseError

from alerts.utils import SmsAlert


class LabResultsForm(CCForm):
    """
    LAB Results Form
    """

    KEYWORDS = {
        'en': ['qr'],
        'rw': ['qr'],
        'fr': ['qr'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_PATIENT

    def process(self, patient):

        if len(self.params) < 3:
            raise ParseError(_(u"Not enough info.Expected: LAB Results "\
                                "Requested"))

        '''
        GET ANY OPEN, LAB REPORT
        USE SAMPLE NUMBER AS IDENTIFIER
        '''
        sample_no = self.params[1]

        try:
            labtest = LabReport.objects.get(sample_no=sample_no)
        except LabReport.DoesNotExist:
            raise ParseError(_(u"Unknown LabTest (%s) Check Sampleno and " \
                                "try again") % sample_no)

        #Check status of the LaB
        if labtest.status != LabReport.STATUS_INPROGRESS:
            raise ParseError(_(u"You can only send report of LabTest that " \
                                 "have been received and marked INPROGRESS"))

        labresults = LabResultsReport(encounter=self.encounter)
        labresults.form_group = self.form_group

        #Get test that was done
        test = labtest.lab_test
        #check If test has predefined results
        if test.defined_results:
            expected_results = dict([(results.result_type.upper(),  \
                                        results.result_type) for results in \
                                    LabTestResults.objects.filter(test=test)])
            valid = []
            unkown = []
            for d in self.params[2:]:
                print "result %s " % d
                obj = expected_results.get(d.upper(), None)
                if obj is not None:
                    valid.append(obj)
                    print obj
                else:
                    unkown.append(d)

            if unkown:
                invalid_str = _(u"Test Result (%(codes)s) outside valid " \
                              "range. Result should be %(exp)s.") % \
                             {'codes': ', '.join(unkown).upper(), \
                              'exp': ', '.join(x for x in \
                                                expected_results).upper()}
                raise ParseError(invalid_str)

            if valid:
                results_string = ', '.join([res for res in valid])
                self.response = _(u"Lab Results for %(hh)s, req %(sn)s \
                                    %(test)s: %(res)s  ") \
                                  % {'hh': \
                                        labtest.encounter.patient.health_id, \
                                     'sn': labtest.sample_no, \
                                     'test': labtest.lab_test.name, \
                                     'res': results_string,
                                    }

                labtest.status = LabReport.STATUS_RESULTS
                labtest.save()
                
                labresults.labtest = labtest
                labresults.results = results_string
                labresults.save()

                #Alert originator of the Message
                if labtest.encounter.chw:
                    r = labtest.encounter.chw.reporter
                    msg = _(u"Lab Results for %(hh)s, req %(sn)s \
                                    %(test)s: %(res)s  ") \
                                  % {'hh': \
                                        labtest.encounter.patient.health_id, \
                                     'sn': labtest.sample_no, \
                                     'test': labtest.lab_test.name, \
                                     'res': results_string,
                                    }
                    alert = SmsAlert(reporter=r, msg=msg)
                    sms_alert = alert.send()

                    sms_alert.name = "Lab Results"
                    sms_alert.save()

        else:
            results_string = ', '.join([res for res in self.params[2:]])

            labtest.status = LabReport.STATUS_RESULTS
            labtest.save()
            
            labresults.labtest = labtest
            labresults.results = results_string
            labresults.save()
                
            self.response = _(u"Lab Results for %(hh)s, req %(sn)s \
                                    %(test)s: %(res)s  ") \
                                  % {'hh': \
                                        labtest.encounter.patient.health_id, \
                                     'sn': labtest.sample_no, \
                                     'test': labtest.lab_test.name, \
                                     'res': results_string,
                                    }

            #Alert originator of the Message
            if labtest.encounter.chw:
                r = labtest.encounter.chw.reporter
                msg = _(u"Lab Results for %(hh)s, req %(sn)s  %(test)s: " \
                          "%(res)s") % {'hh': \
                                        labtest.encounter.patient.health_id, \
                                     'sn': labtest.sample_no, \
                                     'test': labtest.lab_test.name, \
                                     'res': results_string,
                                    }
                alert = SmsAlert(reporter=r, msg=msg)
                sms_alert = alert.send()
                sms_alert.name = "Lab Results"
                sms_alert.save()
