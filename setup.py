from setuptools import setup

setup(
    name="django-massmailer",
    author="Alexandre Macabies",
    license="GPL3",
    packages=["massmailer"],
    install_requires=[
        "bleach",  # HTML sanitizer
        "celery<5",  # task queue
        "django<3",
        "django-reversion",  # model revision/history
        "django-crispy-forms",  # form builder compatible with Bootstrap
        "jinja2",  # sane templates
        "markdown",
        "pyparsing",  # query language parser
        "rules",  # fine-grained permissions
    ],
)
