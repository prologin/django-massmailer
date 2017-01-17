import enum

import bleach
import jinja2
import jinja2.meta
import jinja2.runtime
import locale
import re
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import FieldDoesNotExist
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.text import ugettext_lazy as _, slugify

from mailing.query_parser import parse_query, ParseError
from prologin.utils import override_locale

TEMPLATE_OPTS = {'autoescape': False,
                 'trim_blocks': True,
                 'undefined': jinja2.runtime.StrictUndefined}

RE_TAG = re.compile(r'\{([%#])(.*?)\1\}|\{\{(.*?)\}\}', re.MULTILINE | re.DOTALL)


class TemplateItem(enum.Enum):
    subject = ('subject', {})
    plain = ('plain_body', {})
    html = ('html_body', {'autoescape': True})


class Template(models.Model):
    name = models.CharField(max_length=144, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    subject = models.TextField(verbose_name=_("Subject template"))
    plain_body = models.TextField(verbose_name=_("Plaintext body template"))
    html_body = models.TextField(blank=True, verbose_name=_("HTML body template"))

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

    def template(self, item: TemplateItem):
        return jinja2.Template(source=self.template_source(item), **self.template_opts(item))

    def variables(self, item: TemplateItem):
        ast = jinja2.Environment(**self.template_opts(item)).parse(source=self.template_source(item))
        return jinja2.meta.find_undeclared_variables(ast)

    def render(self, item: TemplateItem, context: dict):
        with override_locale(locale.LC_TIME, 'fr_FR.UTF-8'):
            content = self.template(item).render(context)
        if item is TemplateItem.html:
            content = bleach.linkify(content)
        return content

    def preview(self, item: TemplateItem):
        text = self.template_source(item)

        def replace(match):
            return jinja2.Markup('<span class="placeholder">\u25cc</em>')

        return RE_TAG.sub(replace, text)

    def full_preview(self, context):
        result = {}
        for item in TemplateItem:
            data = {}
            try:
                declared = self.variables(item)
                rendered = self.render(item, context)
                data['context'] = {'declared': list(context.keys() - declared),
                                   'missing': list(declared - context.keys())}
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
        return reverse('mailing:template:update', kwargs={'id': self.pk, 'slug': slugify(self.name)})


class Query(models.Model):
    name = models.CharField(max_length=144, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    query = models.TextField(verbose_name=_("Query"))
    useful_with = models.ManyToManyField(Template, blank=True, related_name='useful_queries',
                                         verbose_name=_("Useful with templates"))

    class Meta:
        ordering = ['name']
        verbose_name = _("Query")
        verbose_name_plural = _("Queries")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('mailing:query:update', kwargs={'id': self.pk, 'slug': slugify(self.name)})

    def get_results(self):
        return self.execute(self.query)

    def parse(self):
        return parse_query(self.query)

    @staticmethod
    def execute(query):
        User = get_user_model()
        user_label = User._meta.label

        result = parse_query(query)
        qs = result.queryset
        qs_label = qs.model._meta.label

        user_qs = qs
        # if queryset is not a User queryset, require a "user" alias
        if user_qs.model != User:
            if 'user' not in result.aliases:
                raise ParseError(_("The root model is not %(model)s. You must provide a `user` alias.") %
                                 {'model': user_label})
            user_field = result.aliases['user']
            try:
                if qs.model._meta.get_field(user_field).related_model != User:
                    raise ParseError(_("%(label)s.%(field)s is not %(model)s") %
                                     {'label': qs_label, 'field': user_field, 'model': user_label})
            except FieldDoesNotExist:
                raise ParseError(_("%(label)s has no field `%(field)s`" % {'label': qs_label, 'field': user_field}))
            user_pks = set(qs.values_list(user_field, flat=True))
            user_qs = User._default_manager.filter(pk__in=user_pks)

        return result, user_qs


def build_emails(template: Template, query: Query, attachments=None):
    User = get_user_model()
    # TODO: attachments
    result, user_qs = query.get_results()
    queryset = result.queryset.order_by('pk')

    if result.queryset.model is User:
        user_getter = lambda object: object
    else:
        user_getter = lambda object: getattr(object, result.aliases['user'])

    for object in queryset:
        context = {alias: getattr(object, field) for alias, field in result.aliases.items()}
        context[result.model_name] = object
        user = user_getter(object)
        email = mail.EmailMessage(
            to=[user.email],
            subject=template.render(TemplateItem.subject, context),
            body=template.render(TemplateItem.plain, context),
            # TODO: html
            headers={'List-Unsubscribe': '<{}>'.format(user.get_unsubscribe_url())},
        )
        yield email
