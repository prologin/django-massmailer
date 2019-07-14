from django import template
from django.http import QueryDict

register = template.Library()


@register.simple_tag
def querystring(request=None, **kwargs):
    if request is None:
        qs = QueryDict().copy()
    else:
        qs = request.GET.copy()
    # Can't use update() here as it would just append to the querystring
    for k, v in kwargs.items():
        qs[k] = v
    return qs.urlencode()
