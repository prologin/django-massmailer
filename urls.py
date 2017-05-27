from django.conf.urls import url, include

import mailing.views

template_patterns = [
    url(r'^$', mailing.views.CreateTemplateView.as_view(), name='new'),
    url(r'^preview/$', mailing.views.TemplatePreviewView.as_view(), name='preview'),
    url(r'^(?P<id>[0-9]+)/', mailing.views.UpdateTemplateView.as_view(), name='update'),
    url(r'^(?P<id>[0-9]+)\-(?P<slug>[\w_-]+)/', mailing.views.UpdateTemplateView.as_view(), name='update'),
]

query_patterns = [
    url(r'^$', mailing.views.CreateQueryView.as_view(), name='new'),
    url(r'^preview/$', mailing.views.QueryPreviewView.as_view(), name='preview'),
    url(r'^(?P<id>[0-9]+)/', mailing.views.UpdateQueryView.as_view(), name='update'),
    url(r'^(?P<id>[0-9]+)\-(?P<slug>[\w_-]+)/', mailing.views.UpdateQueryView.as_view(), name='update'),
]

batch_obj_patterns = [
    url(r'^$', mailing.views.BatchDetailView.as_view(), name='detail'),
    url(r'^retry$', mailing.views.BatchRetryView.as_view(), name='retry-pending'),
    url(r'^delete', mailing.views.BatchDeleteView.as_view(), name='delete'),
]

batch_patterns = [
    url(r'^$', mailing.views.BatchListView.as_view(), name='list'),
    url(r'^new', mailing.views.BatchCreateView.as_view(), name='new'),
    url(r'^(?P<id>[0-9]+)/', include(batch_obj_patterns)),
]

urlpatterns = [
    url(r'^$', mailing.views.DashboardView.as_view(), name='dashboard'),
    url(r'^template/', include(template_patterns, namespace='template')),
    url(r'^query/', include(query_patterns, namespace='query')),
    url(r'^batch/', include(batch_patterns, namespace='batch')),
]
