import os
import sys


filedir = os.path.dirname(__file__)

rootpath = os.path.join(filedir, "..", "..","..") 
sys.path.append(os.path.join(rootpath))
sys.path.append(os.path.join(rootpath,'apps'))
os.environ['RAPIDSMS_INI'] = os.path.join(rootpath,'local.ini')
os.environ['DJANGO_SETTINGS_MODULE'] = 'rapidsms.webui.settings'


from rapidsms.webui import settings

import django.core.handlers.wsgi
application = django.core.handlers.wsgi.WSGIHandler()
