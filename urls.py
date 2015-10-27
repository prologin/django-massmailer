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
    url(r'^context/$', mailing.views.QueryContextView.as_view(), name='context'),
    url(r'^preview/$', mailing.views.QueryPreviewView.as_view(), name='preview'),
    url(r'^(?P<id>[0-9]+)/', mailing.views.UpdateQueryView.as_view(), name='update'),
    url(r'^(?P<id>[0-9]+)\-(?P<slug>[\w_-]+)/', mailing.views.UpdateQueryView.as_view(), name='update'),
]

urlpatterns = [
    url(r'^$', mailing.views.DashboardView.as_view(), name='dashboard'),
    url(r'^template/', include(template_patterns, namespace='template')),
    url(r'^query/', include(query_patterns, namespace='query')),
]
