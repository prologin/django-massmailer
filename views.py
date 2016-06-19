import bleach
import json
import markdown
import traceback
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.db.models import Count, Q
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.text import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import UpdateView, CreateView, ModelFormMixin
from reversion.views import RevisionMixin
from rules.contrib.views import PermissionRequiredMixin

import mailing.forms
import mailing.models
import mailing.query_parser
from mailing.utils import JinjaEscapeExtension
from users.models import search_users


class MailingPermissionMixin(PermissionRequiredMixin):
    permission_required = 'dashboard.admin'


class ObjectByIdMixin:
    def get_object(self, queryset=None):
        return (queryset or self.get_queryset()).get(pk=self.kwargs['id'])


class DashboardView(MailingPermissionMixin, TemplateView):
    template_name = 'mailing/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = mailing.models.Template.objects.annotate(query_count=Count('useful_queries'))
        context['queries'] = mailing.models.Query.objects.annotate(template_count=Count('useful_with'))
        return context


class CreateTemplateView(MailingPermissionMixin, RevisionMixin, CreateView):
    template_name = 'mailing/template/details.html'
    context_object_name = 'template'
    model = mailing.models.Template
    form_class = mailing.forms.TemplateForm

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = template = form.save(commit=False)
        template.author = self.request.user
        template.save()
        return super(ModelFormMixin, self).form_valid(form)


class UpdateTemplateView(MailingPermissionMixin, ObjectByIdMixin, RevisionMixin, UpdateView):
    template_name = 'mailing/template/details.html'
    context_object_name = 'template'
    model = mailing.models.Template
    form_class = mailing.forms.TemplateForm

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

        results = query.execute()
        search = request.POST.get('search', '').strip()
        if search:
            try:
                results = search_users(search, qs=results, throw=True)
            except ValueError:
                pass
        count = results.count()
        data['query'] = {'count': count, 'page': min(count, page)}
        try:
            user = results[page]
            data['render'] = template.full_preview({'user': user})
        except IndexError:
            data['render'] = ''
        return JsonResponse(data)


class CreateQueryView(MailingPermissionMixin, RevisionMixin, CreateView):
    template_name = 'mailing/query/details.html'
    context_object_name = 'query'
    model = mailing.models.Query
    form_class = mailing.forms.QueryForm

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        self.object = query = form.save(commit=False)
        query.author = self.request.user
        query.save()
        return super(ModelFormMixin, self).form_valid(form)


class UpdateQueryView(MailingPermissionMixin, ObjectByIdMixin, RevisionMixin, UpdateView):
    template_name = 'mailing/query/details.html'
    context_object_name = 'query'
    model = mailing.models.Query
    form_class = mailing.forms.QueryForm


class QueryContextView(MailingPermissionMixin, View):
    def get(self, request, *args, **kwargs):
        User = get_user_model()

        def find_user_field(model):
            for field in model._meta.fields:
                try:
                    if field.related_model is User:
                        return field.name
                except AttributeError:
                    pass

        def field_choices(field):
            if hasattr(field, 'choices') and field.choices:
                return [(id, str(label)) for id, label in field.choices]

        models = apps.get_models()
        models = [{'name': str(model._meta.verbose_name_plural.capitalize()),
                   'app': model._meta.app_label,
                   'user_field': find_user_field(model),
                   'label': model._meta.label}
                  for model in models]
        models.sort(key=lambda e: (e['user_field'] is None, e['app'].lower(), e['name'].lower()))

        fields = []
        try:
            fields = [{'name': field.name,
                       'verbose_name': str(field.verbose_name) if hasattr(field, 'verbose_name') else field.name,
                       'help_text': str(field.help_text) if hasattr(field, 'help_text') else '',
                       'choices': field_choices(field),
                       'type': field.__class__.__name__}
                      for field in apps.get_model(request.GET['model'])._meta.get_fields()]
        except Exception:
            pass

        return JsonResponse({
            'models': models,
            'fields': fields,
        })


@method_decorator(csrf_exempt, name='dispatch')
class QueryPreviewView(MailingPermissionMixin, View):
    sample_count = 5

    def post(self, request, *args, **kwargs):
        User = get_user_model()
        query = request.POST['query']
        try:
            qs = mailing.query_parser.parse_query(query, User)
            if qs.model != User:
                raise TypeError("Must be a User queryset")
            count = qs.count()
            sample = json.loads(serializers.get_serializer('json')().serialize(qs[:self.sample_count]))
            data = {'count': count,
                    'query': str(qs.query),
                    'sample': json.dumps(sample, indent=2)}
            status = 200
        except Exception:
            data = {'error': traceback.format_exc(limit=2)}
            status = 400
        return JsonResponse(data, status=status)
