import copy
import re

from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import get_language, ugettext_lazy as _
from reversion.models import Version

import massmailer.models


class TemplateForm(forms.ModelForm):
    html_enabled = forms.BooleanField(
        initial=False, required=False, label=_("HTML enabled")
    )
    use_markdown = forms.BooleanField(
        initial=True, required=False, label=_("Generate HTML from plaintext")
    )
    useful_queries = forms.ModelChoiceField(
        queryset=massmailer.models.Query.objects.all(),
        required=False,
        label=_("Useful queries"),
    )
    # for overwrite checking
    revisions = forms.IntegerField(widget=forms.HiddenInput())

    class Meta:
        model = massmailer.models.Template
        fields = [
            'name',
            'description',
            'subject',
            'plain_body',
            'html_body',
            'language',
        ]
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revisions'].initial = self._revision_count()
        if (
            self.instance
            and self.instance.pk
            and self.instance.html_body.strip()
        ):
            self.fields['html_enabled'].initial = True

        self.fields['language'] = forms.ChoiceField(
            choices=settings.LANGUAGES,
            initial=get_language(),
            widget=forms.Select(),
            required=True,
        )

    def _revision_count(self):
        if self.instance and self.instance.pk:
            return Version.objects.get_for_object(self.instance).count()
        return 0

    def reset_overwritten(self):
        # FIXME: hack
        self.data._mutable = True
        self.data['revisions'] = self._revision_count()
        self.data._mutable = False

    def was_overwritten(self):
        return self.cleaned_data['revisions'] != self._revision_count()

    def clean(self):
        data = self.cleaned_data
        if data['html_enabled'] and not data.get('html_body', '').strip():
            raise forms.ValidationError(
                _("You must provide an HTML template if HTML is enabled.")
            )


class QueryForm(forms.ModelForm):
    class Meta:
        model = massmailer.models.Query
        fields = ['name', 'description', 'useful_with', 'query']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class CreateBatchForm(forms.ModelForm):
    FOOLPROOF_PHRASE = _("i am fine bothering %(n)s people")

    class Meta:
        model = massmailer.models.Batch
        fields = ('name', 'template', 'query')

    @classmethod
    def foolproof_field(cls, count):
        phrase = cls.FOOLPROOF_PHRASE % {'n': count}
        field = forms.CharField(
            label=_("Foolproofing"),
            widget=forms.TextInput(
                attrs={'autocomplete': 'off', 'autofocus': True}
            ),
        )
        field.help_text = _("Type “%s” above") % "\ufeff".join(phrase)
        field.validators.append(RegexValidator(re.escape(phrase)))
        return field

    def foolproof_enabled(self):
        return not settings.DEBUG

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = self.data.copy()

        submit = _("Send")
        submit_cls = "btn-primary"

        if 'query' in self.data and 'template' in self.data:
            # once the form is submitted once, add the foolproof test (we now know the user count)
            query = self.fields['query'].queryset.get(pk=self.data['query'])

            result, user_qs = massmailer.models.Query.execute(query.query)
            count = len(user_qs)
            submit = _("Actually send to %(n)s people right now") % {
                'n': count
            }
            submit_cls = "btn-warning"

            for field in CreateBatchForm.Meta.fields:
                f = self.fields[field]
                name = 'dis_' + field
                disabled_copy = copy.deepcopy(f)  # add a disabled copy
                disabled_copy.disabled = True
                self.fields[name] = disabled_copy
                self.initial[name] = self.data[field]  # copy value
                f.widget = forms.HiddenInput()  # hide original data

            if not self.data.get('name'):
                # generate a nice name
                template = self.fields['template'].queryset.get(
                    pk=self.data['template']
                )
                name = '{} ⋅ {} ⋅ {}'.format(
                    template, query, timezone.now().date()
                )
                self.data['name'] = self.initial['name'] = self.initial[
                    'dis_name'
                ] = name

            if self.foolproof_enabled():
                # add foolproof
                self.fields['foolproof'] = self.foolproof_field(count)

        self.helper = FormHelper(self)
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-4'
        self.helper.field_class = 'col-lg-8'
        # add the submit button
        self.helper.layout.append(
            StrictButton(
                format_html('<i class="fa fa-paper-plane-o"></i> {}', submit),
                type="submit",
                css_class="{} btn-block".format(submit_cls),
            )
        )
