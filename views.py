import bleach
import json
import inspect
import markdown
import traceback
import pyparsing

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.exceptions import FieldError, ObjectDoesNotExist
from django.db import models
from django.db import transaction
from django.db.models import Count
from django.http.response import JsonResponse, Http404
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.text import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import UpdateView, CreateView, ModelFormMixin, DeleteView
from django.views.generic.list import ListView
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin

import mailing.forms
import mailing.models
import mailing.tasks
import mailing.query_parser
from mailing.utils import JinjaEscapeExtension


class MailingPermissionMixin(PermissionRequiredMixin):
    permission_required = 'mailing.admin'


class ObjectByIdMixin:
    def get_object(self, queryset=None):
        try:
            return (queryset or self.get_queryset()).get(pk=self.kwargs['id'])
        except ObjectDoesNotExist:
            raise Http404()


class DashboardView(MailingPermissionMixin, TemplateView):
    template_name = 'mailing/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = mailing.models.Template.objects.annotate(query_count=Count('useful_queries'))
        context['queries'] = mailing.models.Query.objects.annotate(template_count=Count('useful_with'))
        return context


class TemplateMixin(MailingPermissionMixin, RevisionMixin):
    template_name = 'mailing/template/details.html'
    context_object_name = 'template'
    model = mailing.models.Template
    form_class = mailing.forms.TemplateForm


class CreateTemplateView(TemplateMixin, CreateView):
    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = template = form.save(commit=False)
        template.author = self.request.user
        template.save()
        return super(ModelFormMixin, self).form_valid(form)


class UpdateTemplateView(TemplateMixin, ObjectByIdMixin, UpdateView):
    def form_valid(self, form):
        if form.was_overwritten():
            form.reset_overwritten()
            form.add_error(None, _("The form was modified and saved while you were editing. "
                                   "Please merge with current version."))
            return self.form_invalid(form)
        return super().form_valid(form)


@method_decorator(csrf_exempt, name='dispatch')
class TemplatePreviewView(MailingPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        # TODO: context from query builder
        data = {}
        html_enabled = request.POST.get('html_enabled') == 'true'

        query = mailing.models.Query.objects.get(pk=(request.POST['query']))
        page = int(request.POST['page'])

        template = mailing.models.Template()
        template.subject = request.POST['subject']
        template.plain_body = request.POST['plain']

        if html_enabled:
            if request.POST.get('use_markdown') == 'true':
                md = markdown.Markdown(extensions=[JinjaEscapeExtension()])
                html = data['html_template'] = md.convert(bleach.clean(template.plain_body))
            else:
                html = request.POST['html']
            template.html_body = html

        results, user_qs = query.get_results()
        qs = results.queryset
        count = qs.count()
        user_count = user_qs.count()
        data['query'] = {'count': count, 'user_count': user_count, 'page': min(count, page)}
        try:
            object = qs[page]
            context = {alias: getattr(object, field) for alias, field in results.aliases.items()}
            context[results.model_name] = object
            data['render'] = template.full_preview(context)
        except IndexError:
            data['render'] = ''
        return JsonResponse(data)


class QueryMixin(MailingPermissionMixin, RevisionMixin):
    template_name = 'mailing/query/details.html'
    context_object_name = 'query'
    model = mailing.models.Query
    form_class = mailing.forms.QueryForm

    @cached_property
    def available_enums(self):
        return sorted(({'name': name,
                        'members': [m.name for m in enum]}
                       for name, enum in mailing.query_parser.available_enums.items()), key=lambda e: e['name'].lower())

    @cached_property
    def available_funcs(self):
        return [{'name': name, 'doc': inspect.signature(func)}
                for name, func in mailing.query_parser.available_funcs.items()]

    @cached_property
    def available_models(self):
        User = get_user_model()

        def find_user_field(model):
            for field in model._meta.fields:
                try:
                    if field.related_model is User:
                        return field.name
                except AttributeError:
                    pass

        models = apps.get_models()
        models = ({'name': str(model._meta.verbose_name_plural.capitalize()),
                   'cls_name': model.__name__,
                   'app': model._meta.app_label,
                   'is_user': model is User,
                   'user_field': find_user_field(model),
                   'label': model._meta.label}
                  for model in models)
        return sorted(models,
                      key=lambda e: (not e['is_user'], e['user_field'] is None, e['app'].lower(), e['name'].lower()))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_enums'] = self.available_enums
        context['available_funcs'] = self.available_funcs
        context['available_models'] = self.available_models
        return context


class CreateQueryView(QueryMixin, CreateView):
    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = query = form.save(commit=False)
        query.author = self.request.user
        query.save()
        return super(ModelFormMixin, self).form_valid(form)


class UpdateQueryView(QueryMixin, ObjectByIdMixin, UpdateView):
    pass


@method_decorator(csrf_exempt, name='dispatch')
class QueryPreviewView(MailingPermissionMixin, View):
    @staticmethod
    def serialize(obj):
        if obj is None:
            return None
        if not isinstance(obj, models.Model):
            return None
        return json.loads(serializers.get_serializer('json')().serialize([obj]))[0]

    def post(self, request, *args, **kwargs):
        query = request.POST['query']
        page = int(request.POST['page'])
        try:
            # run the query
            result, user_qs = mailing.models.Query.execute(query)
            qs = result.queryset
            count = qs.count()
            user_count = user_qs.count()
            instance = None
            if 0 <= page < count:
                obj = qs[page]
                instance = {result.model_name: self.serialize(obj)}
                for name, field in result.aliases.items():
                    serialized = self.serialize(getattr(obj, field))
                    if serialized:
                        instance[name] = serialized

            data = {'count': count,
                    'user_count': user_count,
                    'model': qs.model._meta.label,
                    'model_name': result.model_name,
                    'aliases': list(result.aliases.items()),
                    'query': str(qs.query),
                    'result': instance}
        except Exception as e:
            if isinstance(e, (mailing.query_parser.ParseError, FieldError)):
                error = str(e)
            elif isinstance(e, pyparsing.ParseException):
                error = _("Syntax error at position %(pos)s.") % {'pos': e.loc}
            else:
                error = traceback.format_exc(limit=2)
            data = {'error': error}
        return JsonResponse(data)


class BatchListView(PermissionRequiredMixin, ListView):
    model = mailing.models.Batch
    template_name = 'mailing/batch-list.html'
    context_object_name = 'batches'
    paginate_by = 25
    permission_required = 'mailing.admin'


class BatchCreateView(PermissionRequiredMixin, CreateView):
    model = mailing.models.Batch
    form_class = mailing.forms.CreateBatchForm
    template_name = 'mailing/batch-create.html'
    permission_required = 'mailing.send'

    def get_success_url(self):
        return reverse('mailing:batch:detail', args=[self.object.pk])

    def form_valid(self, form):
        with transaction.atomic():
            # create the batch
            batch = form.save(commit=False)
            batch.initiator = self.request.user
            batch.save()

            emails = list(batch.build_emails())
            # create the batch emails
            mailing.models.BatchEmail.objects.bulk_create(emails)

        # create the tasks
        for email in emails:
            email.send_task()

        return super().form_valid(form)


class BatchDetailView(PermissionRequiredMixin, ListView):
    model = mailing.models.BatchEmail
    template_name = 'mailing/batch-emails.html'
    context_object_name = 'emails'
    paginate_by = 200
    permission_required = 'mailing.admin'

    @property
    def batch_id(self):
        return self.kwargs['id']

    @cached_property
    def batch(self):
        return (mailing.models.Batch.objects.prefetch_related('emails')
                .annotate(email_count=Count('emails'))
                .get(pk=self.batch_id))

    def get_queryset(self):
        return self.batch.emails.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        return context


class BatchRetryView(PermissionRequiredMixin, UpdateView):
    model = mailing.models.Batch
    pk_url_kwarg = 'id'
    fields = []
    success_url = reverse_lazy('mailing:batch:list')
    permission_required = 'mailing.send'

    def form_valid(self, form):
        # create the tasks
        for email in self.get_object().pending_emails():
            email.send_task()
        return super(ModelFormMixin, self).form_valid(form)


class BatchDeleteView(PermissionRequiredMixin, DeleteView):
    model = mailing.models.Batch
    pk_url_kwarg = 'id'
    success_url = reverse_lazy('mailing:batch:list')
    permission_required = 'mailing.send'
