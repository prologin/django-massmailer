import csv
import mailbox
import sys

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Remove and deactivate bounces from ~/Mailbox"

    def handle(self, *args, **options):
        inbox = mailbox.Maildir('~/Maildir', factory=None)
        for msg in inbox.itervalues():
            if (msg.is_multipart() and len(msg.get_payload()) > 1 and
                    msg.get_payload(1).get_content_type() ==
                    'message/delivery-status'):

                if len(msg.get_payload()) > 2:
                    msg = msg.get_payload(2)

                try:
                    while len(msg.get_payload()) > 0 and 'To' not in msg:
                            msg = msg.get_payload(0)
                    email = msg['To']
                    print(email)
                    try:
                        user = User.get(email__iexact=email)
                        user.is_active = False
                        user.allow_mailing = False
                        user.save()
                        print('  -> User {} deactivated.'.format(user))
                    except User.DoesNotExist:
                        print('  -> User not found.'.format(user))

                except: # wtf?
                    pass
