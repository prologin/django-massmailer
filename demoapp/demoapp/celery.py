from celery import Celery
from django.conf import settings

app = Celery('demoapp')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
