from contextlib import contextmanager


@contextmanager
def override_locale(category, lang):
    import locale
    current = locale.getlocale(category)
    locale.setlocale(category, lang)
    yield
    locale.setlocale(category, current)
