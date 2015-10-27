from django import forms
from django.utils.translation import ugettext_lazy as _
from reversion.models import Version

import mailing.models


class TemplateForm(forms.ModelForm):
    html_enabled = forms.BooleanField(initial=False, required=False, label=_("HTML enabled"))
    use_markdown = forms.BooleanField(initial=True, required=False, label=_("Generate HTML from plaintext"))
    useful_queries = forms.ModelChoiceField(queryset=mailing.models.Query.objects.all(), required=False, label=_("Useful queries"))
    # for overwrite checking
    revisions = forms.IntegerField(widget=forms.HiddenInput())

    class Meta:
        model = mailing.models.Template
        fields = ['name', 'description', 'subject', 'plain_body', 'html_body']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revisions'].initial = self._revision_count()
        if self.instance and self.instance.pk and self.instance.html_body.strip():
            self.fields['html_enabled'].initial = True

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
            raise forms.ValidationError(_("You must provide an HTML template if HTML is enabled."))


class QueryForm(forms.ModelForm):
    class Meta:
        model = mailing.models.Query
        fields = ['name', 'description', 'query', 'useful_with']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}
