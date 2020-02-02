from django.views.generic import RedirectView

from demoapp.models import SubscriberEmail


class NewsletterUnsubscribeView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return reverse('')

    def get(self, request, *args, **kwargs):
        try:
            subscriber = SubscriberEmail.objects.get(email=kwargs['email'])

            if subscriber.unsubscribe_token == kwargs['token']:
                subscriber.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    _('Successfully unsubscribed from newsletter.'),
                )
            else:
                messages.add_message(
                    request,
                    messages.ERROR,
                    _('Failed to unsubscribe: wrong token.'),
                )
        except SubscriberEmail.DoesNotExist:
            messages.add_message(
                request,
                messages.ERROR,
                _('Failed to unsubscribe: unregistered address'),
            )

        return super().get(request, *args, **kwargs)
