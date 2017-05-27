from celery import shared_task
from django.db import transaction
from prologin.utils.db import lock_model

import mailing.models


@shared_task(bind=True, default_retry_delay=30, max_retries=1, ignore_result=True)
def send_email(self, id):
    with transaction.atomic():
        # prevent django/celery race
        lock_model(mailing.models.BatchEmail)

        email = mailing.models.BatchEmail.objects.get(pk=id)
        if not email.pending:
            return

        try:
            email.build_email().send(fail_silently=False)
        except Exception as exc:
            raise self.retry(exc=exc)

        email.state = mailing.models.MailState.sent.value
        email.save()
