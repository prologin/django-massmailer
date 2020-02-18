from django.views.generic import RedirectView

from demoapp.models import SubscriberEmail
from django.shortcuts import redirect


class NewsletterUnsubscribeView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return '/'

    def get(self, request, *args, **kwargs):
        try:
            subscriber = SubscriberEmail.objects.get(email=kwargs['email'])

            if subscriber.unsubscribe_token == kwargs['token']:
                subscriber.delete()
                print('Successfully unsubscribed from newsletter.')
            else:
                print('Failed to unsubscribe: wrong token.')
        except SubscriberEmail.DoesNotExist:
            print('Failed to unsubscribe: unregistered address')
        return super().get(request, *args, **kwargs)
