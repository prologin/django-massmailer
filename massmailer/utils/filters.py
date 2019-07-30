import babel
import babel.dates
import jinja2


def get_locale(ctx):
    language_code = ctx['language']
    return babel.Locale.parse(language_code, sep='-')


@jinja2.contextfilter
def format_datetime(ctx, date, format='full'):
    locale = get_locale(ctx)
    return babel.dates.format_datetime(date, format=format, locale=locale)


@jinja2.contextfilter
def format_date(ctx, date, format='full'):
    locale = get_locale(ctx)
    return babel.dates.format_date(date, format=format, locale=locale)


@jinja2.contextfilter
def format_time(ctx, date, format='full'):
    locale = get_locale(ctx)
    return babel.dates.format_time(date, format=format, locale=locale)
