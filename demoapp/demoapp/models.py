import hashlib

from django.conf import settings
from django.db import models
from django.urls import reverse


class SubscriberEmail(models.Model):
    email = models.EmailField()

    @property
    def unsubscribe_token(self):
        secret = settings.SECRET_KEY.encode()
        unique = f"{self.id}{settings.SECRET_KEY}"
        return hashlib.sha256(unique.encode()).hexdigest()[:32]

    @property
    def get_unsubscribe_url(self):
        return reverse(
            'news_unsubscribe',
            kwargs={'email': self.email, 'token': self.unsubscribe_token},
        )

    def __str__(self):
        return self.email
