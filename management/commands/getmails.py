import csv
import sys

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Get e-mails and required attributes of users from a request"

    def add_arguments(self, parser):
        # TODO: way to add filters to the request
        parser.add_argument('--related',
                help='Related tables separated by commas')
        parser.add_argument('fields', nargs='*', default=('email',),
                help='The model fields needed for the mailing')

    def handle(self, *args, **options):
        fields = options['fields']
        related = options['related']
        related = related.split(',') if related is not None else []
        User = get_user_model()
        users = (User.objects.filter(allow_mailing=True)
                             .select_related(*related))
        writer = csv.DictWriter(sys.stdout, fieldnames=fields)
        writer.writeheader()
        for u in users:
            writer.writerow({f: getattr(u, f) for f in fields})
