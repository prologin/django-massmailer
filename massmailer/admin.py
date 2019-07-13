from reversion.admin import VersionAdmin

from django.contrib import admin
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _

import massmailer.models


class TemplateAdmin(VersionAdmin):
    exclude = ['author']


class QueryAdmin(VersionAdmin):
    exclude = ['author', 'useful_with']


class BatchEmailInline(admin.TabularInline):
    model = massmailer.models.BatchEmail
    fields = readonly_fields = ['id', 'user', 'to', 'state_display']
    extra = max_num = 0
    can_delete = False


class BatchAdmin(admin.ModelAdmin):
    inlines = [BatchEmailInline]
    raw_id_fields = ['initiator']
    search_fields = ['initiator__username', 'template__name', 'query__name']
    list_display = ['__str__', 'initiator', 'date_created', 'email_count']
    list_filter = ['template', 'query']

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('initiator')
            .prefetch_related('emails')
            .annotate(email_count=Count('emails'))
        )

    def email_count(self, obj):
        return obj.email_count

    email_count.short_description = _("Email count")
    email_count.admin_order_field = 'email_count'


admin.site.register(massmailer.models.Template, TemplateAdmin)
admin.site.register(massmailer.models.Query, QueryAdmin)
admin.site.register(massmailer.models.Batch, BatchAdmin)
