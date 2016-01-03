import csv
import sys
from traceback import print_exc

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from djmail.models import Message, STATUS_SENT

from prologin.email import send_email


class Command(BaseCommand):
    help = "Get e-mails and required attributes of users from a request"

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.queries = ['all', 'test', 'exclude-pattern']
        self.actions = ['export', 'send']
        self.templates = ['start_contest', "end_qualifications"]

    def add_arguments(self, parser):
        parser.add_argument('--query', default='test', choices=self.queries,
                            help='The query to use among: {}'.format(self.queries))
        parser.add_argument('--pattern', default=None,
                            help='The pattern to search for in body text, for --query exclude-pattern')
        parser.add_argument('--template', default=None, choices=self.templates,
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
                self.stderr.write('error: wrong answer.')
                sys.exit(1)

        if options['query'] == 'all':
            pass
        elif options['query'] == 'exclude-pattern':
            if not options['pattern']:
                self.stderr.write("--pattern option is required")
                sys.exit(1)
            already_sent = Message.objects.filter(status=STATUS_SENT, body_text__icontains=options['pattern'])
            already_sent = set(already_sent.values_list('to_email', flat=True))
            query = query.exclude(email__in=already_sent)
        elif options['query'] == 'test':
            query = query.filter(email='association@prologin.org')

        if not query.count():
            self.stderr.write('error: query returned no result')
            sys.exit(1)

        action = options['action']
        if action not in self.actions:
            self.stderr.write('error: action unknown: {}'.format(action))
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
            self.stderr.write('error: wrong or no template given.')
            sys.exit(1)
        if not options['dry'] and ((input('You are ACTUALLY sending a mail to '
                  '{} people. Type "This is fine" to confirm: '
                  .format(len(basequery)))).lower() != 'this is fine'):
            self.stderr.write('error: wrong answer.')
            sys.exit(1)

        for i, u in enumerate(basequery, 1):
            self.stdout.write('Sending mail to "{}" <{}> ({} / {})'
                    .format(u.username, u.email, i, len(basequery)))
            if not options['dry']:
                try:
                    raise Exception
                    send_email('mailing/{}'.format(options['template']),
                            u.email, {'user': u})
                except:
                    print_exc()
