from django.urls import path, include

import massmailer.views

app_name = 'massmailer'

template_patterns = [
    path('', massmailer.views.CreateTemplateView.as_view(), name='new'),
    path(
        'preview',
        massmailer.views.TemplatePreviewView.as_view(),
        name='preview',
    ),
    path(
        '<int:id>',
        massmailer.views.UpdateTemplateView.as_view(),
        name='update',
    ),
    path(
        '<int:id>-<slug>',
        massmailer.views.UpdateTemplateView.as_view(),
        name='update',
    ),
]

query_patterns = [
    path('', massmailer.views.CreateQueryView.as_view(), name='new'),
    path(
        'preview', massmailer.views.QueryPreviewView.as_view(), name='preview'
    ),
    path(
        '<int:id>', massmailer.views.UpdateQueryView.as_view(), name='update'
    ),
    path(
        '<int:id>-<slug>',
        massmailer.views.UpdateQueryView.as_view(),
        name='update',
    ),
]

batch_obj_patterns = [
    path('', massmailer.views.BatchDetailView.as_view(), name='detail'),
    path(
        'retry',
        massmailer.views.BatchRetryView.as_view(),
        name='retry-pending',
    ),
    path('delete', massmailer.views.BatchDeleteView.as_view(), name='delete'),
]

batch_patterns = [
    path('', massmailer.views.BatchListView.as_view(), name='list'),
    path('new', massmailer.views.BatchCreateView.as_view(), name='new'),
    path('<int:id>/', include(batch_obj_patterns)),
]

urlpatterns = [
    path('', massmailer.views.DashboardView.as_view(), name='dashboard'),
    path(
        'template/',
        include((template_patterns, app_name), namespace='template'),
    ),
    path('query/', include((query_patterns, app_name), namespace='query')),
    path('batch/', include((batch_patterns, app_name), namespace='batch')),
]
