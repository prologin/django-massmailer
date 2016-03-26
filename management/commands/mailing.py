import collections

import csv
import sys
import traceback

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.template import Template, Context
from django.utils import translation
from djmail.models import Message, STATUS_SENT

from contest.models import Assignation
from documents.models import generate_tex_pdf
from prologin.email import send_email
import contest.models


class Command(BaseCommand):
    help = "Get e-mails and required attributes of users from a request"

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.queries = ['all', 'test', 'exclude-pattern', 'semifinal_qualified',
            'semifinal_ruled_out', 'final_qualified']
        self.actions = ['export', 'send', 'send_semifinal_qualified']
        self.templates = ['start_contest', 'end_qualifications',
            'semifinal_not_qualified']

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

        parser.add_argument('action', help='Action to use among: [{}]'.format(self.actions))

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

        # TODO(halfr): refactor
        if options['query'] == 'all':
            pass
        # TODO(halfr): remove legacy
        elif options['query'] == 'exclude-pattern':
            if not options['pattern']:
                self.stderr.write("--pattern option is required")
                sys.exit(1)
            already_sent = Message.objects.filter(status=STATUS_SENT, body_text__icontains=options['pattern'])
            already_sent = set(already_sent.values_list('to_email', flat=True))
            query = query.exclude(email__in=already_sent)
        elif options['query'] == 'test':
            query = query.filter(email='association+test@prologin.org')
        elif options['query'] == 'semifinal_ruled_out':
            query = query.filter(contestants__edition__year=2016,
                contestants__assignation_semifinal=Assignation.ruled_out.value)
        elif options['query'] == 'final_qualified':
            query = query.filter(contestants__edition__year=2016,
                contestants__assignation_final=Assignation.assigned.value)

        if options['action'] == 'send_semifinal_qualified':
            query = query.filter(contestants__edition__year=2016,
                contestants__assignation_semifinal=Assignation.assigned.value)

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

    def check_user_brain(self, query):
        msg = ('You are ACTUALLY sending a mail to {} people. '
               'Type "This is fine" to confirm: '.format(len(query)))
        if input(msg).lower() != 'this is fine':
            self.stderr.write('error: wrong answer.')
            sys.exit(1)

    def send(self, basequery, *args, **options):
        if options['template'] not in self.templates:
            self.stderr.write('error: wrong or no template given.')
            sys.exit(1)

        self.check_user_brain(basequery)

        for i, u in enumerate(basequery, 1):
            self.stdout.write('Sending mail to "{}" <{}> ({} / {})'
                              .format(u.username, u.email, i, len(basequery)))
            if not options['dry']:
                try:
                    ctx = {'user': u, 'year': 2016,
                           'train_url': settings.SITE_BASE_URL + '/train',
                           'forum_url': settings.SITE_BASE_URL + '/forum',
                    }
                    send_email('mailing/{}'.format(options['template']),
                               u.email, ctx)
                except:
                    traceback.print_exc()

    def send_semifinal_qualified(self, qualified, *args, **options):
        self.check_user_brain(qualified)

        # For date formatting in templates
        translation.activate('fr')

        for i, user in enumerate(qualified, 1):
            self.stdout.write('Sending mail to "{}" <{}> ({} / {})'
                              .format(user.username, user.email, i, len(qualified)))

            # TODO: refactor with document module
            locations = collections.defaultdict(list)
            semifinals = list(contest.models.Event.objects
                              .select_related('edition')
                              .filter(edition__year=settings.PROLOGIN_EDITION,
                                      type=contest.models.Event.Type.semifinal.value))
            for event in semifinals:
                locations[event.date_begin.date()].append(event.center.city)
            locations = [(k, ', '.join(v).title()) for k, v in locations.items()]
            contestant = user.contestants.get(edition__year=2016)
            event = contestant.assignation_semifinal_event
            center = event.center

            ctx = {
                'user': user,
                'items': [contestant],
                'event': event,
                'center': center,
                'locations': locations,
                'year': 2016,
                'url': settings.SITE_BASE_URL + '/train',
            }
            with generate_tex_pdf('documents/droit-image-regionale.tex', ctx) as portayal_agreement_content:
                with generate_tex_pdf('documents/convocation-regionale.tex', ctx) as convocation_content:
                    attachements = (
                        ('Prologin2016ConvocationRegionale.pdf', convocation_content.read(), 'application/pdf'),
                        ('Prologin2016DroitImage.pdf', portayal_agreement_content.read(), 'application/pdf'),
                    )
                    try:
                        if options['dry']:
                            continue
                        send_email('mailing/semifinal_qualified', user.email, ctx, attachements)
                    except:
                        traceback.print_exc()
