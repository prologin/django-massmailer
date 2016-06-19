from django.contrib import admin
from reversion.admin import VersionAdmin

import mailing.models


class TemplateAdmin(VersionAdmin):
    exclude = ['author']


class QueryAdmin(VersionAdmin):
    exclude = ['author', 'useful_with']


admin.site.register(mailing.models.Template, TemplateAdmin)
admin.site.register(mailing.models.Query, QueryAdmin)
