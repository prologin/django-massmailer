import os.path
from setuptools import setup, find_namespace_packages

with open(os.path.join(os.path.dirname(__file__), "README.md"), "r") as fh:
    long_description = fh.read()

setup(
    name="django-massmailer",
    version='0.4',
    author="Association Prologin",
    author_email="info@prologin.org",
    license="GPL3",
    packages=find_namespace_packages(include=['massmailer.*']),
    include_package_data=True,
    description=(
        "A standalone Django app to send templated emails in batch. "
        "Features a custom query engine and template editor with preview."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "babel",  # i18n template filters
        "bleach",  # HTML sanitizer
        "celery>4",  # task queue
        "django-bootstrap-breadcrumbs",  # breadcrumbs in default templates
        "django-crispy-forms",  # form builder compatible with Bootstrap
        "django-reversion",  # model revision/history
        "django>=2.1",
        "jinja2",  # sane templates
        "markdown",
        "pyparsing",  # query language parser
    ],
    classifiers=[
        'Environment :: Web Environment',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Framework :: Django',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'Topic :: Communications :: Email',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    project_urls={
        'Source': 'https://github.com/prologin/django-massmailer/',
        'Issue Tracker': 'https://github.com/prologin/django-massmailer/issues',
    },
)
