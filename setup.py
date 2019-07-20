from setuptools import setup

setup(
    name="django-massmailer",
    author="Association Prologin",
    author_email="info@prologin.org",
    license="GPL3",
    packages=["massmailer"],
    install_requires=[
        "bleach",  # HTML sanitizer
        "celery>4",  # task queue
        "django>=2.1",
        "django-bootstrap-breadcrumbs",  # breadcrumbs in default templates
        "django-reversion",  # model revision/history
        "django-crispy-forms",  # form builder compatible with Bootstrap
        "jinja2",  # sane templates
        "markdown",
        "pyparsing",  # query language parser
        "rules",  # fine-grained permissions
    ],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Development Status :: 4 - Alpha',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'Topic :: Communications :: Email',
    ],
)
