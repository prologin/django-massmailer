import bleach
import json
import inspect
import markdown
import traceback
import pyparsing

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import (
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
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
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import (
    UpdateView,
    CreateView,
    ModelFormMixin,
    DeleteView,
)
from django.views.generic.list import ListView
from reversion.views import RevisionMixin

import massmailer.forms
import massmailer.models
import massmailer.tasks
from massmailer.query_parser import QueryParser
from massmailer.utils import JinjaEscapeExtension


class MailerAdminMixin(UserPassesTestMixin):
    def test_func(self):
        # Like for the Django Admin, only staff users can see the mailing
        # panel, whatever their permissions are.
        return self.request.user.is_staff


class ObjectByIdMixin:
    def get_object(self, queryset=None):
        try:
            return (queryset or self.get_queryset()).get(pk=self.kwargs['id'])
        except ObjectDoesNotExist:
            raise Http404()


class DashboardView(MailerAdminMixin, TemplateView):
    template_name = 'massmailer/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = massmailer.models.Template.objects.annotate(
            query_count=Count('useful_queries')
        )
        context['queries'] = massmailer.models.Query.objects.annotate(
            template_count=Count('useful_with')
        )
        return context


class TemplateMixin(MailerAdminMixin, RevisionMixin):
    template_name = 'massmailer/template/details.html'
    context_object_name = 'template'
    model = massmailer.models.Template
    form_class = massmailer.forms.TemplateForm


class CreateTemplateView(PermissionRequiredMixin, TemplateMixin, CreateView):
    permission_required = 'massmailer.create_template'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = template = form.save(commit=False)
        template.author = self.request.user
        template.save()
        return super(ModelFormMixin, self).form_valid(form)

    def get_object(self):
        return None  # the template isn't in db yet


class UpdateTemplateView(
    PermissionRequiredMixin, TemplateMixin, ObjectByIdMixin, UpdateView
):
    permission_required = 'massmailer.change_template'

    def form_valid(self, form):
        if form.was_overwritten():
            form.reset_overwritten()
            form.add_error(
                None,
                _(
                    "The form was modified and saved while you were editing. "
                    "Please merge with current version."
                ),
            )
            return self.form_invalid(form)
        return super().form_valid(form)


@method_decorator(csrf_exempt, name='dispatch')
class TemplatePreviewView(PermissionRequiredMixin, MailerAdminMixin, View):
    permission_required = 'massmailer.view_template'

    def post(self, request, *args, **kwargs):
        # TODO: context from query builder
        data = {}

        if not request.user.has_perm('massmailer.view_query'):
            data['error'] = _(
                "You don't have the permission to view query results."
            )
            return JsonResponse(data)

        html_enabled = request.POST.get('html_enabled') == 'true'

        query = massmailer.models.Query.objects.get(pk=(request.POST['query']))
        page = int(request.POST['page'])

        template = massmailer.models.Template()
        template.subject = request.POST['subject']
        template.plain_body = request.POST['plain']
        template.language = request.POST['language']

        if html_enabled:
            if request.POST.get('use_markdown') == 'true':
                md = markdown.Markdown(extensions=[JinjaEscapeExtension()])
                html = data['html_template'] = md.convert(
                    bleach.clean(template.plain_body)
                )
            else:
                html = request.POST['html']
            template.html_body = html

        results, user_qs = query.get_results()
        qs = results.queryset
        count = qs.count()
        user_count = user_qs.count()
        data['query'] = {
            'count': count,
            'user_count': user_count,
            'page': min(count, page),
        }
        try:
            object = qs[page]
            context = {
                alias: getattr(object, field)
                for alias, field in results.aliases.items()
            }
            context[results.model_name] = object
            data['render'] = template.full_preview(context)
        except IndexError:
            data['render'] = ''
        return JsonResponse(data)


class QueryMixin(MailerAdminMixin, RevisionMixin):
    template_name = 'massmailer/query/details.html'
    context_object_name = 'query'
    model = massmailer.models.Query
    form_class = massmailer.forms.QueryForm

    @cached_property
    def available_enums(self):
        return sorted(
            (
                {'name': name, 'members': [m.name for m in enum]}
                for name, enum in QueryParser().available_enums.items()
            ),
            key=lambda e: e['name'].lower(),
        )

    @cached_property
    def available_funcs(self):
        return [
            {
                'name': name,
                'doc': inspect.getdoc(func),
                'signature': inspect.signature(func),
            }
            for name, func in QueryParser().available_funcs.items()
        ]

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
        models = (
            {
                'name': str(model._meta.verbose_name_plural.capitalize()),
                'cls_name': model.__name__,
                'app': model._meta.app_label,
                'is_user': model is User,
                'user_field': find_user_field(model),
                'label': model._meta.label,
                'doc': inspect.getdoc(model),
            }
            for model in models
        )
        return sorted(
            models,
            key=lambda e: (
                not e['is_user'],
                e['user_field'] is None,
                e['app'].lower(),
                e['name'].lower(),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_enums'] = self.available_enums
        context['available_funcs'] = self.available_funcs
        context['available_models'] = self.available_models
        context['user_model'] = get_user_model().__name__
        return context


class CreateQueryView(PermissionRequiredMixin, QueryMixin, CreateView):
    permission_required = 'massmailer.create_query'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = query = form.save(commit=False)
        query.author = self.request.user
        query.save()
        return super(ModelFormMixin, self).form_valid(form)

    def get_object(self):
        return None  # the query isn't in the db yet


class UpdateQueryView(
    PermissionRequiredMixin, QueryMixin, ObjectByIdMixin, UpdateView
):
    permission_required = 'massmailer.change_query'


@method_decorator(csrf_exempt, name='dispatch')
class QueryPreviewView(PermissionRequiredMixin, MailerAdminMixin, View):
    permission_required = 'massmailer.view_query'

    @staticmethod
    def serialize(obj):
        if obj is None:
            return None
        if not isinstance(obj, models.Model):
            return None
        return json.loads(
            serializers.get_serializer('json')().serialize([obj])
        )[0]

    def post(self, request, *args, **kwargs):
        query = request.POST['query']
        page = int(request.POST['page'])
        try:
            # run the query
            result, user_qs = massmailer.models.Query.execute(query)
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

            data = {
                'count': count,
                'user_count': user_count,
                'model': qs.model._meta.label,
                'model_name': result.model_name,
                'aliases': list(result.aliases.items()),
                'query': str(qs.query),
                'result': instance,
            }
        except Exception as e:
            if isinstance(e, (massmailer.query_parser.ParseError, FieldError)):
                error = str(e)
            elif isinstance(e, pyparsing.ParseException):
                error = _("Syntax error at position %(pos)s.") % {'pos': e.loc}
            else:
                error = traceback.format_exc(limit=2)
            data = {'error': error}
        return JsonResponse(data)


class BatchListView(PermissionRequiredMixin, MailerAdminMixin, ListView):
    model = massmailer.models.Batch
    template_name = 'massmailer/batch-list.html'
    context_object_name = 'batches'
    paginate_by = 25
    permission_required = 'massmailer.view_batch'


class BatchCreateView(PermissionRequiredMixin, MailerAdminMixin, CreateView):
    model = massmailer.models.Batch
    form_class = massmailer.forms.CreateBatchForm
    template_name = 'massmailer/batch-create.html'
    permission_required = 'massmailer.create_batch'

    def get_success_url(self):
        return reverse('massmailer:batch:detail', args=[self.object.pk])

    def form_valid(self, form):
        with transaction.atomic():
            # create the batch
            batch = form.save(commit=False)
            batch.initiator = self.request.user
            batch.save()

            emails = list(batch.build_emails())
            # create the batch emails
            massmailer.models.BatchEmail.objects.bulk_create(emails)

        # create the tasks
        for email in emails:
            email.send_task()

        return super().form_valid(form)

    def get_object(self):
        return None  # the batch isn't in the db yet


class BatchDetailView(PermissionRequiredMixin, MailerAdminMixin, ListView):
    model = massmailer.models.BatchEmail
    template_name = 'massmailer/batch-emails.html'
    context_object_name = 'emails'
    paginate_by = 200
    permission_required = 'massmailer.view_batch'

    @property
    def batch_id(self):
        return self.kwargs['id']

    @cached_property
    def batch(self):
        return (
            massmailer.models.Batch.objects.prefetch_related('emails')
            .annotate(email_count=Count('emails'))
            .get(pk=self.batch_id)
        )

    def get_queryset(self):
        return self.batch.emails.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        return context


class BatchRetryView(PermissionRequiredMixin, MailerAdminMixin, UpdateView):
    model = massmailer.models.Batch
    pk_url_kwarg = 'id'
    fields = []
    success_url = reverse_lazy('massmailer:batch:list')
    permission_required = 'massmailer.change_batch'

    def form_valid(self, form):
        # create the tasks
        for email in self.get_object().pending_emails():
            email.send_task()
        return super(ModelFormMixin, self).form_valid(form)


class BatchDeleteView(PermissionRequiredMixin, MailerAdminMixin, DeleteView):
    model = massmailer.models.Batch
    pk_url_kwarg = 'id'
    success_url = reverse_lazy('massmailer:batch:list')
    permission_required = 'massmailer.delete_batch'
