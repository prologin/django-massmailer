from django.contrib import admin
from django.urls import path, include
from demoapp import views

NEWSLETTER_PATTERNS = [
    path(
        'unsubscribe/<str:email>/<str:token>/',
        views.NewsletterUnsubscribeView.as_view(),
        name='news_unsubscribe',
    )
]

urlpatterns = [
    path('newsletter/', include(NEWSLETTER_PATTERNS)),
    path('admin/', admin.site.urls),
    path('', include('massmailer.urls')),
]
