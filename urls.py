from django.urls import path, include

import mailing.views

app_name = 'mailing'

template_patterns = [
    path('', mailing.views.CreateTemplateView.as_view(), name='new'),
    path('preview', mailing.views.TemplatePreviewView.as_view(), name='preview'),
    path('<int:id>', mailing.views.UpdateTemplateView.as_view(), name='update'),
    path('<int:id>-<slug>', mailing.views.UpdateTemplateView.as_view(), name='update'),
]

query_patterns = [
    path('', mailing.views.CreateQueryView.as_view(), name='new'),
    path('preview', mailing.views.QueryPreviewView.as_view(), name='preview'),
    path('<int:id>', mailing.views.UpdateQueryView.as_view(), name='update'),
    path('<int:id>-<slug>', mailing.views.UpdateQueryView.as_view(), name='update'),
]

batch_obj_patterns = [
    path('', mailing.views.BatchDetailView.as_view(), name='detail'),
    path('retry', mailing.views.BatchRetryView.as_view(), name='retry-pending'),
    path('delete', mailing.views.BatchDeleteView.as_view(), name='delete'),
]

batch_patterns = [
    path('', mailing.views.BatchListView.as_view(), name='list'),
    path('new', mailing.views.BatchCreateView.as_view(), name='new'),
    path('<int:id>/', include(batch_obj_patterns)),
]

urlpatterns = [
    path('', mailing.views.DashboardView.as_view(), name='dashboard'),
    path('template/', include((template_patterns, app_name), namespace='template')),
    path('query/', include((query_patterns, app_name), namespace='query')),
    path('batch/', include((batch_patterns, app_name), namespace='batch')),
]
