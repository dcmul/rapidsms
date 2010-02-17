#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
from datetime import date

from django.db import models
from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.utils import clean_names, DOBProcessor
from childcount.models import Patient
from childcount.exceptions import BadValue, ParseError
from childcount.forms.utils import MultipleChoiceField


class PatientRegistrationForm(CCForm):
    KEYWORDS = {
        'en': ['new'],
    }
    MIN_HH_AGE = 10
    MIN_GUARDIAN_AGE = 10

    gender_field = MultipleChoiceField()
    gender_field.add_choice('en', Patient.GENDER_MALE, 'M')
    gender_field.add_choice('en', Patient.GENDER_FEMALE, 'F')

    SELF_HH = {}
    SELF_HH['en'] = 'P'

    SURNAME_FIRST = False

    def pre_process(self, health_id):

        chw = self.message.persistant_connection.reporter.chw
        try:
            p = Patient.objects.get(health_id__iexact=health_id)
        except Patient.DoesNotExist:
            pass
        else:
            raise BadValue(_(u"That health ID has already been registered to "\
                              "%(patient)s by %(chw)s") % \
                             {'patient': p, 'chw': p.chw})

        patient = Patient()
        patient.health_id = health_id
        patient.chw = chw
        patient.location = chw.location
        tokens = self.params[1:]

        lang = self.message.reporter.language

        expected = _(u"given_names surname gender age or date_of_birth " \
                      "and head_of_household")

        if len(tokens) < 4:
            raise ParseError(_(u"Not enough info. You must send: " \
                                "%(expected)s") % {'expected': expected})

        self.gender_field.set_language(lang)

        gender_indexes = []
        i = 0
        for token in tokens:
            if token in self.gender_field.valid_choices():
                gender_indexes.append(i)
            i += 1

        if len(gender_indexes) == 0:
            raise ParseError(_(u"You must indicate gender after the name " \
                                "with a %(choices)s") % \
                              {'choices': self.gender_field.choices_string()})

        dob = None
        for i in gender_indexes:
            # the gender field is at the end of the tokens.  We don't know
            # what to do about this.
            if i == len(tokens) - 1:
                raise ParseError(_(u"Could not understand your message. " \
                                    "Expected %(expected)s") % \
                                    {'expected': expected})

            dob, variance = DOBProcessor.from_age_or_dob(lang, tokens[i + 1])

            if dob:
                patient.dob = dob
                days, weeks, months = patient.age_in_days_weeks_months()
                if days < 60 and variance > 1:
                    raise BadValue(_(u"Please provide an exact birth date " \
                                      "for children under 2 months"))
                elif months < 24 and variance > 30:
                    raise BadValue(_(u"Please provide an exact birth date " \
                                      "or the age in months for children " \
                                      "under two years"))

        if not dob:
            raise ParseError(_(u"Could not understand age or " \
                                    "date_of_birth of %(string)s") % \
                                    {'string': tokens[i + 1]})

        patient.estimated_dob = variance > 1

        # if the gender field is the first or second
        if i == 0 or i == 1:
            raise ParseError(_(u"You must provide more than one name for " \
                                "the patient."))

        patient.last_name, patient.first_name, alias = \
                             clean_names(' '.join(tokens[:i]), \
                             surname_first=self.SURNAME_FIRST)

        # remove the name tokens
        tokens = tokens[i:]

        # remove the gender token
        patient.gender = self.gender_field.get_db_value(tokens.pop(0))

        # remove the age token
        tokens.pop(0)

        if len(tokens) == 0:
            raise ParseError(_(u"You must indicate the head of " \
                                "household after the age. If this " \
                                "is the head of household " \
                                "write %(char)s after the dob/age.") % \
                                {'char': self.SELF_HH[lang]})

        household = tokens.pop(0)
        self_hoh = False
        if household == self.SELF_HH[lang].lower():
            if patient.years() < self.MIN_HH_AGE:
                raise BadValue(_(u"This patient is too young to be a head of "\
                                  "household. Please indicate their head of" \
                                  "household"))
            patient.household = patient
            self_hoh = True

        # Patient is not a head of household
        else:
            try:
                patient.household = Patient.objects.get( \
                                                health_id__iexact=household)
            except Patient.DoesNotExist:
                raise BadValue(_(u"Could not find head of household " \
                                  "with health ID %(id)s. You must " \
                                  "register the head of household " \
                                  "first") % \
                                  {'id': household})

            age = patient.household.years()
            if age < self.MIN_HH_AGE:
                raise BadValue(_(u"The head of household you specified is " \
                                  "too young to be a head of household " \
                                  "(%(hh)s)") % {'hh': patient.household})

            # if the household head they listed is not a head of household
            if patient.household.household != patient.household:
                raise BadValue(_(u"The head of household you specified " \
                                  "(%(hh)s) is not a head of household. " \
                                  "Their head of household is (%(hhhh)s). " \
                                  "If they are the head, set their head of " \
                                  "household to %(char)s") % \
                                  {'hh': patient.household, \
                                   'hhhh': patient.household.household, \
                                   'char': self.SELF_HH[lang]})

        if patient.years() < 5:
            if len(tokens) == 0:
                raise BadValue(_(u"This child is less than 5 years. You " \
                                  "must indicate their parent or " \
                                  "guardian's health ID after their " \
                                  "head of household ID"))
            guardian = tokens.pop(0)

            try:
                patient.guardian = Patient.objects.get( \
                                                health_id__iexact=guardian)
            except Patient.DoesNotExist:
                raise BadValue(_(u"Could not find mother / guardian " \
                                  "with health ID %(id)s. You must " \
                                  "register the mother first.") % \
                                  {'id': household})
            if patient.guardian < self.MIN_GUARDIAN_AGE:
                raise BadValue(_(u"The mother / guardian you specified is " \
                                  "too young to be a mother." \
                                  "(%(hh)s)") % {'hh': patient.household})

        patient_check = Patient.objects.filter( \
                                first_name__iexact=patient.first_name, \
                                last_name__iexact=patient.last_name, \
                                dob=patient.dob)

        if len(patient_check) > 0:
            old_p = patient_check[0]
            if old_p.chw == chw:
                patient_chw = _(u"you")
            else:
                patient_chw = patient_check[0].chw
            raise BadValue(_(u"%(name)s %(sex)s/%(age)s was already " \
                              "registered by %(chw)s. Their health id is " \
                              "%(id)s") % \
                              {'name': old_p.full_name(), \
                               'sex': old_p.gender, \
                               'age': old_p.humanised_age(), \
                               'chw': patient_chw, \
                               'id': old_p.health_id.upper()})
        patient.save()
        if self_hoh:
            patient.household = patient
            patient.save()
        print patient.household

        response = _("You successfuly registered %(patient)s") % \
                    {'patient': patient}
        return response