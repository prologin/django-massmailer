from django.contrib import admin

import demoapp.models as models


@admin.register(models.SubscriberEmail)
class SubscriberEmailAdmin(admin.ModelAdmin):
    search_fields = ['email']
