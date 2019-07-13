import celery

from django.db import transaction

from massmailer.models import MailState, BatchEmail


@celery.shared_task(
    bind=True,
    ignore_result=True,
    default_retry_delay=60,
    max_retries=2,
    soft_time_limit=10,
    time_limit=60,
)
def send_email(self, mail_id):
    def set_state(old_state, new_state):
        with transaction.atomic():
            try:
                email = BatchEmail.objects.get(
                    pk=mail_id, state=old_state.value
                )
            except BatchEmail.DoesNotExist:
                return None
            email.state = new_state.value
            email.save()
        return email

    # atomically push to *sending* queue
    email = set_state(MailState.pending, MailState.sending)
    if not email:
        # deleted or already sent
        return

    python_mail = email.build_email()

    try:
        # this can take a long time or fail
        ret = python_mail.send(fail_silently=False)
        if not ret:
            raise RuntimeError(
                "mail.send() should have returned a truthful value; returned {}".format(
                    ret
                )
            )
    except Exception as exc:
        # atomically push to *pending* queue (for retry)
        if not set_state(MailState.sending, MailState.pending):
            # deleted or already pending or already sent
            return
        raise self.retry(exc=exc)

    # mark as sent
    set_state(MailState.sending, MailState.sent)
