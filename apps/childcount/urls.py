from django.conf.urls.defaults import *
from django.contrib import admin
import childcount.views as views
import childcount.reports as reports

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
    url(r'^childcount/?$', views.index),
    url(r'^childcount/reports?$', reports.reports),
    (r'^report/(?P<report_name>[a-z\-\_]+)/(?P<object_id>\d*)$', reports.report_view),
    #last_30_days
    (r'^last_30_days/$', reports.last_30_days),
    (r'^last_30_days/(?P<object_id>\d*)$', reports.last_30_days),
    (r'^last_30_days/per_page/(?P<per_page>\d*)$', reports.last_30_days),
    (r'^last_30_days/per_page/(?P<per_page>\d*)/(?P<d>\d*)$', reports.last_30_days),
    #patients_by_chw
    (r'^patients_by_chw/$', reports.patients_by_chw),
    (r'^patients_by_chw/(?P<object_id>\d*)$', reports.patients_by_chw),
    (r'^patients_by_chw/per_page/(?P<per_page>\d*)$', reports.patients_by_chw),
    (r'^patients_by_chw/(?P<object_id>\d*)/(?P<rformat>[a-z]*)$', reports.patients_by_chw),
    #last_30_days
    (r'^measles_summary/$', reports.measles_summary),
    (r'^measles_summary/(?P<object_id>\d*)$', reports.measles_summary),
    (r'^measles_summary/per_page/(?P<per_page>\d*)$', reports.measles_summary),
    (r'^measles_summary/per_page/(?P<per_page>\d*)/(?P<d>\d*)$', reports.measles_summary),
    #patients_by_chw
    (r'^measles/$', reports.measles),
    (r'^measles/(?P<object_id>\d*)$', reports.measles),
    (r'^measles/per_page/(?P<per_page>\d*)$', reports.measles),
    (r'^measles/(?P<object_id>\d*)/(?P<rformat>[a-z]*)$', reports.measles),
    #patients_by_chw
    (r'^malaria/$', reports.malaria),
    (r'^malaria/(?P<object_id>\d*)$', reports.malaria),
    (r'^malaria/per_page/(?P<per_page>\d*)$', reports.malaria),
    (r'^malaria/(?P<object_id>\d*)/(?P<rformat>[a-z]*)$', reports.malaria),
    #patients_by_chw
    (r'^malnut/$', reports.malnut),
    (r'^malnut/(?P<object_id>\d*)$', reports.malnut),
    (r'^malnut/per_page/(?P<per_page>\d*)$', reports.malnut),
    (r'^malnut/(?P<object_id>\d*)/(?P<rformat>[a-z]*)$', reports.malnut),
   
    #patients_by_age
    (r'^List_Enfant_Age/$', reports.patients_by_age),
    (r'^List_Enfant_Age/(?P<object_id>\d*)$', reports.patients_by_age),
    (r'^List_Enfant_Age/per_page/(?P<per_page>\d*)$', reports.patients_by_age),
    (r'^List_Enfant_Age/(?P<object_id>\d*)/(?P<rformat>[a-z]*)$', reports.patients_by_age),
    # commands shortlist
    (r'^childcount/commands-shortlist', views.commands_pdf),
    #malnutrition_screening
    (r'^malnutrition_screening/$', reports.malnutrition_screening),
)

