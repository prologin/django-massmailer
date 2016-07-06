from enum import Enum
import csv
import mailbox
import sys

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class DeactivateStatus(Enum):
    Deactivated = 'deactivated'
    AlreadyDeactivated = 'already deactivated'
    UserNotFound = 'user not found'

class Command(BaseCommand):
    help = "Disable and deactivate bouncing email addresses"

    def add_arguments(self, parser):
        parser.add_argument('-f', '--from-file', help='Read emails from a file')
        parser.add_argument('-d', '--from-maildir', help='Extract bouncing ' \
                            'addresses from the specified Maildir formatted ' \
                            'directory. Usually: ~/Maildir')

    def deactivate(self, user_email):
        try:
            user = User.objects.get(email__iexact=user_email)
        except User.DoesNotExist:
            return DeactivateStatus.UserNotFound

        already_deactivated = not (user.is_active and user.allow_mailing)
        user.is_active = False
        user.allow_mailing = False
        user.save()
        if already_deactivated:
            return DeactivateStatus.AlreadyDeactivated
        else:
            return DeactivateStatus.Deactivated

    def deactivate_list(self, emails):
        stats = {
            DeactivateStatus.Deactivated: 0,
            DeactivateStatus.AlreadyDeactivated: 0,
            DeactivateStatus.UserNotFound: 0
        }
        print("Deactivating:")
        for email in emails:
            print('  {}'.format(email))
            ret = self.deactivate(email)
            print('    {}: {}.'.format(email, ret.value))
            stats[ret] += 1

        print("\nStats:")
        print("  Deactivated:         {}".format(
            stats[DeactivateStatus.Deactivated]))
        print("  Already deactivated: {}".format(
            stats[DeactivateStatus.AlreadyDeactivated]))
        print("  User not found:      {}".format(
            stats[DeactivateStatus.UserNotFound]))
        print("  Total:               {}".format(sum(stats.values())))

    def from_maildir(self, dirname):
        """Get addresses from bouncing emails stored in ``dirname``"""
        addresses = set()

        inbox = mailbox.Maildir(dirname, factory=None)
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
                    addresses.add(email)
                except Exception: # wtf?
                    import traceback
                    traceback.print_exc()

        return addresses

    def from_stream(self, stream):
        """Get emails addresses from a newline separated list in a file."""
        addresses = set()

        for line in stream:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            addresses.add(line)

        return addresses

    def handle(self, *args, **options):
        if options['from_file']:
            with open(options['from_file']) as f:
                addresses = self.from_stream(f)
        elif options['from_maildir']:
            addresses = self.from_maildir(options['from_maildir'])
        else:
            addresses = set(args)

        self.deactivate_list(addresses)
