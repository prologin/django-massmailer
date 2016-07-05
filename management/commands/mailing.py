import collections

import csv
import sys
import os
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

from documents.models import generate_tex_pdf
from prologin.email import send_email
import contest.models
import mailing.models


class Command(BaseCommand):
    help = "Send predefined email templates to users selected by a predefined query"

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.actions = ['list-templates', 'list-queries', 'send']

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(help='command to launch', dest='cmd')
        subparsers.required = True  # Python consistency.
        subparsers.add_parser('list-queries', help='list queries', cmd=self)
        subparsers.add_parser('list-templates', help='list templates', cmd=self)
        send = subparsers.add_parser('send', help='send mailing', cmd=self)
        send.add_argument('-q', '--query', required=True, help='the query ID to use')
        send.add_argument('-t', '--template', required=True, help='the template ID to use')
        send.add_argument('-f', '--force', action='store_true', help='skip the screen/tmux check')
        send.add_argument('-n', '--dry-run', action='store_true',
                          help='do not actually send the mails')

    def handle(self, *args, **options):
        getattr(self, 'handle_%s' % options['cmd'].replace('-', '_'))(*args, **options)

    def print_list(self, iterable, width=4):
        self.stdout.write('─' * width + '─╮')
        item = None
        while True:
            item = item or next(iterable, None)
            if item:
                pk, error, lines = item
                ((self.stderr if error else self.stdout)
                 .write("\n".join("{pk:>{w}} │ {l}".format(pk=pk if i == 0 else "", w=width, l=line)
                                  for i, line in enumerate(lines))))
                item = next(iterable, None)
                if item:
                    self.stdout.write('─' * width + '─┤')
                else:
                    break
        self.stdout.write('─' * width + '─╯')

    def handle_list_queries(self, *args, **options):
        def queries():
            for query in mailing.models.Query.objects.all():
                try:
                    parsed = query.parse()
                except Exception:
                    error = True
                    aliases = "invalid query"
                else:
                    error = False
                    aliases = "Aliases: {}".format(", ".join(parsed.aliases.keys()))
                yield (
                    query.pk, error, (query.name, query.description.replace("\n", "").replace("\r", "")[:80], aliases))

        self.print_list(queries())

    def handle_list_templates(self, *args, **options):
        def templates():
            for template in mailing.models.Template.objects.all().prefetch_related('useful_queries'):
                useful = "Useful with queries: {}".format(
                    ", ".join(str(pk) for pk in template.useful_queries.values_list('pk', flat=True)))
                yield (template.pk, False, (template.name,
                                            template.description.replace("\n", "").replace("\r", "")[:80],
                                            useful))

        self.print_list(templates())

    def handle_send(self, *args, **options):
        if not options['force']:
            self.check_tmux()

        try:
            query = mailing.models.Query.objects.get(pk=options['query'])
        except mailing.models.Query.DoesNotExist:
            raise CommandError("This query ID does not exist")
        try:
            template = mailing.models.Template.objects.get(pk=options['template'])
        except mailing.models.Template.DoesNotExist:
            raise CommandError("This template ID does not exist")
        self.stdout.write("Using query: {}: {}".format(query.pk, query.name))
        self.stdout.write("Using template: {}: {}".format(template.pk, template.name))

        result, user_qs = query.get_results()
        queryset = result.queryset.order_by('pk')
        count = len(queryset)

        if not options['dry_run']:
            self.check_user_brain(len(queryset), len(user_qs))

        for i, email in enumerate(mailing.models.build_emails(template, query), start=1):
            addr = email.to[0]
            self.stdout.write("{:>5}/{} To: {}".format(i, count, addr))
            if options['dry_run']:
                self.stdout.write("")
                self.stdout.write("To: " + addr)
                self.stdout.write("Subject: " + email.subject)
                self.stdout.write(email.body)
                self.stdout.write("-" * 79)
            else:
                try:
                    email.send()
                except:
                    self.stderr.write(traceback.format_exc())

    def check_tmux(self):
        if not (os.environ.get('TMUX') or os.environ.get('STY')):
            raise CommandError("This command has to be run in screen or tmux")

    def export(self, basequery, *args, **options):
        fields = options['fields'].split(',')
        writer = csv.DictWriter(sys.stdout, fieldnames=fields)
        writer.writeheader()
        for u in basequery:
            writer.writerow({f: getattr(u, f) for f in fields})

    def check_user_brain(self, mail_count, user_count):
        msg = ('You are ACTUALLY sending {} mails to {} users. '
               'Type "This is fine" to confirm: '.format(mail_count, user_count))
        if input(msg).strip().lower() != 'this is fine':
            raise CommandError('wrong answer')

    def send_semifinal_qualified(self, qualified, *args, **options):
        # THIS FUNCTION IS BROKEN
        # TODO: refactor this into something generic
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
