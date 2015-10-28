import csv
import sys

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from prologin.email import send_email


class Command(BaseCommand):
    help = "Get e-mails and required attributes of users from a request"

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.queries = ['all', 'test']
        self.actions = ['export', 'send']
        self.templates = ['start_contest']

    def add_arguments(self, parser):
        parser.add_argument('--query', default='testasso',
                help='The query to use among: {}'.format(self.queries))
        parser.add_argument('--template', default=None,
                help='The template to use among: {}'.format(self.templates))
        parser.add_argument('--dry', action='store_true',
                help='Do not actually send the mails.')
        parser.add_argument('--force-all', action='store_true',
                help='Even for users who did not check the Allow Mailing box')
        parser.add_argument('--fields', default='email',
                help='The model fields wanted in the export separated by commas')

        parser.add_argument('action', help='Action to use among: [{}]'
                .format(self.actions))

    def handle(self, *args, **options):
        query = get_user_model().objects.all()
        if not options['force_all']:
            query = query.filter(allow_mailing=True)
        else:
            if (input('Warning: users who do not want to receive mails ARE '
                      'INCLUDED in this list. Type "This is fine" to confirm: '
                      ).lower() != 'this is fine'):
                print('error: wrong answer.')
                sys.exit(1)

        if options['query'] == 'all':
            pass
        elif options['query'] == 'testasso':
            query = query.filter(email='association@prologin.org')

        action = options['action']
        if action not in self.actions:
            print('error: action unknown: {}'.format(action))
            sys.exit(1)
        getattr(self, action)(query, *args, **options)

    def export(self, basequery, *args, **options):
        fields = options['fields'].split(',')
        writer = csv.DictWriter(sys.stdout, fieldnames=fields)
        writer.writeheader()
        for u in basequery:
            writer.writerow({f: getattr(u, f) for f in fields})

    def send(self, basequery, *args, **options):
        if options['template'] not in self.templates:
            print('error: wrong or no template given.')
            sys.exit(1)
        if not options['dry'] and ((input('You are ACTUALLY sending a mail to '
                  '{} people. Type "This is fine" to confirm: '
                  .format(len(basequery)))).lower() != 'this is fine'):
            print('error: wrong answer.')
            sys.exit(1)

        for i, u in enumerate(basequery, 1):
            print('Sending mail to "{}" <{}> ({} / {})'
                    .format(u.username, u.email, i, len(basequery)))
            if not options['dry']:
                send_email('mailing/{}'.format(options['template']),
                        u.email, {'user': u})

