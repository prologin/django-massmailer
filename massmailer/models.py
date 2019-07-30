import bleach
import enum
import jinja2
import jinja2.meta
import jinja2.runtime
import jinja2.sandbox
import operator
import re
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import FieldDoesNotExist
from django.urls import reverse
from django.db import models
from django.db.models import Count, F, BooleanField
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from functools import reduce

from massmailer.query_parser import QueryParser, ParseError
from massmailer.utils.db import ConditionalSum, CaseMapping
from massmailer.utils import filters as mfilters

TEMPLATE_OPTS = {
    'autoescape': False,
    'trim_blocks': True,
    'undefined': jinja2.runtime.StrictUndefined,
}

VARIABLE_PLACEHOLDER = '<span class="placeholder">\u25cc</span>'
RE_TAG = re.compile(
    r'\{([%#])(.*?)\1\}|\{\{(.*?)\}\}', re.MULTILINE | re.DOTALL
)


class MailState(enum.IntEnum):
    pending = 1
    sending = 2
    sent = 3
    delivered = 4
    bounced = 5
    complained = 6

    @classmethod
    def bad(cls):
        return {cls.bounced, cls.complained}


class TemplateItem(enum.Enum):
    subject = ('subject', {})
    plain = ('plain_body', {})
    html = ('html_body', {'autoescape': True})


class Template(models.Model):
    name = models.CharField(max_length=144, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    subject = models.TextField(verbose_name=_("Subject template"))
    plain_body = models.TextField(verbose_name=_("Plaintext body template"))
    html_body = models.TextField(
        blank=True, verbose_name=_("HTML body template")
    )
    language = models.CharField(max_length=10, verbose_name=_("Language"))

    class Meta:
        ordering = ['name']
        verbose_name = _("Template")
        verbose_name_plural = _("Templates")

    def __str__(self):
        return self.name

    @staticmethod
    def template_opts(item: TemplateItem):
        _, specific_opts = item.value
        opts = TEMPLATE_OPTS.copy()
        opts.update(specific_opts)
        return opts

    @property
    def html_enabled(self):
        return bool(self.html_body.strip())

    def template_source(self, item: TemplateItem):
        attr, _ = item.value
        return getattr(self, attr)

    def environment(self, item):
        env = jinja2.sandbox.SandboxedEnvironment(**self.template_opts(item))
        env.filters['format_datetime'] = mfilters.format_datetime
        env.filters['format_date'] = mfilters.format_date
        env.filters['format_time'] = mfilters.format_time
        return env

    def template(self, item: TemplateItem):
        env = self.environment(item)
        return env.from_string(source=self.template_source(item))

    def variables(self, item: TemplateItem):
        env = self.environment(item)
        ast = env.parse(source=self.template_source(item))
        return jinja2.meta.find_undeclared_variables(ast)

    def render(self, item: TemplateItem, context: dict):
        context['language'] = self.language
        content = self.template(item).render(context)
        if item is TemplateItem.html:
            content = bleach.linkify(content)
        return content

    def preview(self, item: TemplateItem):
        text = self.template_source(item)

        def replace(match):
            return jinja2.Markup(VARIABLE_PLACEHOLDER)

        return RE_TAG.sub(replace, text)

    def full_preview(self, context):
        result = {}
        for item in TemplateItem:
            data = {}
            try:
                declared = self.variables(item)
                rendered = self.render(item, context)
                data['context'] = {
                    'declared': list(context.keys() - declared),
                    'missing': list(declared - context.keys()),
                }
                data['content'] = rendered
            except jinja2.UndefinedError as error:
                data['error'] = {'type': 'undefined', 'msg': error.message}
            except jinja2.TemplateSyntaxError as error:
                data['error'] = {'type': 'syntax', 'msg': error.message}
            except Exception as error:
                data['error'] = {'type': 'other', 'msg': str(error)}
            result[item.name] = data
        return result

    def subject_preview(self):
        return self.preview(TemplateItem.subject)

    def plain_preview(self):
        return self.preview(TemplateItem.plain)

    def html_preview(self):
        return self.preview(TemplateItem.html)

    def get_absolute_url(self):
        return reverse(
            'massmailer:template:update',
            kwargs={'id': self.pk, 'slug': slugify(self.name)},
        )


class Query(models.Model):
    name = models.CharField(max_length=144, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    query = models.TextField(verbose_name=_("Query"))
    useful_with = models.ManyToManyField(
        Template,
        blank=True,
        related_name='useful_queries',
        verbose_name=_("Useful with templates"),
    )

    class Meta:
        ordering = ['name']
        verbose_name = _("Query")
        verbose_name_plural = _("Queries")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            'massmailer:query:update',
            kwargs={'id': self.pk, 'slug': slugify(self.name)},
        )

    def get_results(self):
        return self.execute(self.query)

    def parse(self):
        return QueryParser().parse_query(self.query)

    @staticmethod
    def execute(query):
        User = get_user_model()
        user_label = User._meta.label

        result = QueryParser().parse_query(query)
        qs = result.queryset
        qs_label = qs.model._meta.label

        user_qs = qs
        # if queryset is not a User queryset, require a "user" alias
        if user_qs.model != User:
            if 'user' not in result.aliases:
                raise ParseError(
                    _(
                        "The root model is not %(model)s. You must provide a `user` alias."
                    )
                    % {'model': user_label}
                )
            user_field = result.aliases['user']
            try:
                if qs.model._meta.get_field(user_field).related_model != User:
                    raise ParseError(
                        _("%(label)s.%(field)s is not %(model)s")
                        % {
                            'label': qs_label,
                            'field': user_field,
                            'model': user_label,
                        }
                    )
            except FieldDoesNotExist:
                raise ParseError(
                    _(
                        "%(label)s has no field `%(field)s`"
                        % {'label': qs_label, 'field': user_field}
                    )
                )
            user_pks = set(qs.values_list(user_field, flat=True))
            user_qs = User._default_manager.filter(pk__in=user_pks)

        return result, user_qs


class BatchManager(models.Manager):
    def get_queryset(self):
        total = F('email_count')
        ecount = lambda e: F('{}_email_count'.format(e))

        qs = (
            super()
            .get_queryset()
            .select_related('query', 'template', 'initiator')
            .prefetch_related('emails')
        )

        def annotate(key, value):
            nonlocal qs
            qs = qs.annotate(**{key: value})

        def annotate_count(name, expr):
            count_field = ecount(name)
            annotate(count_field.name, expr)
            annotate('{}_percentage'.format(name), 100.0 * count_field / total)

        annotate(total.name, Count('emails'))

        for state in MailState:
            annotate_count(
                state.name, ConditionalSum(emails__state=state.value)
            )

        annotate_count('unsent', ecount('pending') + ecount('sending'))
        annotate_count(
            'erroneous',
            reduce(
                operator.add, (ecount(state.name) for state in MailState.bad())
            ),
        )
        annotate(
            'completed',
            CaseMapping(
                ecount('unsent').name,
                [(0, True)],
                default=False,
                output_field=BooleanField(),
            ),
        )
        return qs


class Batch(models.Model):
    name = models.CharField(
        max_length=140, blank=True, verbose_name=_("Optional name")
    )
    template = models.ForeignKey(
        Template,
        null=True,
        on_delete=models.SET_NULL,
        related_name='batches',
        verbose_name=_("Template"),
    )
    query = models.ForeignKey(
        Query,
        null=True,
        on_delete=models.SET_NULL,
        related_name='batches',
        verbose_name=_("Query"),
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='massmailer_batches',
    )
    date_created = models.DateTimeField(default=timezone.now, null=False)

    class Meta:
        ordering = ['-date_created']
        verbose_name = _("Batch")
        verbose_name_plural = _("Batches")

    objects = BatchManager()

    @property
    def default_name(self):
        return _("Batch %(id)s") % {'id': self.pk}

    def __str__(self):
        return self.name or self.default_name

    def pending_emails(self):
        return self.emails.filter(state=MailState.pending.value)

    @property
    def erroneous_emails(self):
        return self.emails.filter(
            state__in=[state.value for state in MailState.bad()]
        )

    def build_emails(self):
        result, user_qs = self.query.get_results()
        queryset = result.queryset.order_by('pk')

        if result.queryset.model is get_user_model():
            user_getter = lambda object: object
        else:
            user_getter = lambda object: getattr(
                object, result.aliases['user']
            )

        html_enabled = self.template.html_enabled

        for object in queryset:
            context = {
                alias: getattr(object, field)
                for alias, field in result.aliases.items()
            }
            context[result.model_name] = object
            user = user_getter(object)
            yield BatchEmail(
                batch=self,
                user=user,
                to=user.email,
                subject=self.template.render(TemplateItem.subject, context),
                body=self.template.render(TemplateItem.plain, context),
                html_body=self.template.render(TemplateItem.html, context)
                if html_enabled
                else "",
            )


class BatchEmail(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.PositiveIntegerField(
        db_index=True, default=MailState.pending.value
    )
    batch = models.ForeignKey(
        Batch, related_name='emails', on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    to = models.EmailField(
        blank=False
    )  # in case user is deleted or changes email
    subject = models.TextField(blank=True)
    body = models.TextField(blank=True)
    html_body = models.TextField(blank=True, default="")

    class Meta:
        ordering = ['state']

    def __str__(self):
        return '[{}] {}'.format(self.state_display, self.id)

    @property
    def state_display(self):
        return MailState(self.state).name

    @property
    def task_id(self):
        return 'massmailer-{}'.format(self.pk)

    @property
    def pending(self):
        return self.state == MailState.pending.value

    def build_email(self):
        assert self.subject
        assert self.body
        # add a custom header to resolve the mail ID from bounces/complaints
        headers = {'X-MID': self.id}
        if self.user and hasattr(self.user, 'get_unsubscribe_url'):
            headers['List-Unsubscribe'] = '<{}>'.format(
                self.user.get_unsubscribe_url()
            )

        kwargs = {
            'to': [self.to],
            'subject': self.subject,
            'body': self.body,
            'headers': headers,
        }

        if self.html_body:
            email = mail.EmailMultiAlternatives(**kwargs)
            email.attach_alternative(self.html_body, 'text/html')
        else:
            email = mail.EmailMessage(**kwargs)
        return email

    def send_task(self):
        from massmailer.tasks import send_email

        return send_email.apply_async(args=[self.pk], task_id=self.task_id)
