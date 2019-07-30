# django-massmailer

[![Build Status](https://travis-ci.com/prologin/django-massmailer.svg?branch=master)](https://travis-ci.com/prologin/django-massmailer)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

`django-massmailer` is a standalone Django app that you can plug in your
website to send e-mails in bulk. It features:

- An **e-mail template engine** to write your e-mail template, supporting both
  plaintext and HTML, with a live preview:

    ![Template engine demo](https://github.com/prologin/django-massmailer/raw/master/doc/template_demo.gif)

- A **query language** to select the subset of users you want to send e-mails
  to, and preview the list of selected users:

    ![Query language demo](https://github.com/prologin/django-massmailer/raw/master/doc/query_demo.gif)

- A **batch status report** that shows how many e-mails have been sent, and is
  able to track bounces.

    ![Batch status demo](https://github.com/prologin/django-massmailer/raw/master/doc/batch_demo.png)


## Installation

First, install `django-massmailer` and its Python dependencies:

```
pip install django-massmailer
```

Then, add `massmailer` and its Django dependencies to your project's
`INSTALLED_APPS`:

```python
INSTALLED_APPS = (
    # ...
    'massmailer',
    'crispy_forms',
    'django_bootstrap_breadcrumbs',
    'reversion',
)
```

Add the following URL pattern to your `urls.py` to put the mailing
dashboard in `/mailing`:

```python
urlpatterns = [
    # ...
    path('mailing', include('massmailer.urls')),
]
```

Then, execute the migrations to create the massmailer models:

```bash
python3 manage.py migrate
```

You also need to have a working Celery setup with your website.
You can check out the [official
tutorial](https://docs.celeryproject.org/en/latest/django/first-steps-with-django.html)
to setup Celery in your Django website, or just look at how we do it in our demo
application:

- [`demoapp/__init__.py`](https://github.com/prologin/django-massmailer/blob/master/demoapp/demoapp/__init__.py)
- [`demoapp/celery.py`](https://github.com/prologin/django-massmailer/blob/master/demoapp/demoapp/celery.py)
- [`demoapp/settings.py`](https://github.com/prologin/django-massmailer/blob/master/demoapp/demoapp/settings.py)

## How to use

### Permissions

Only staff users can see the mailing dashboard. By default, only superusers can
use anything in massmailer. There are three categories of permissions you
can grant to some staff users to allow them to make changes:

- `mailing.{view,create,change,delete}_template` to view, create, change and
  delete templates.
- `mailing.{view,create,change,delete}_query` to view, create, change and
  delete queries.
  **⚠ These permissions give access to personal user data. ⚠**
- `mailing.{view,create,change,delete}_batch` to view, send, change and
  delete batches.
  **⚠ These permissions give access to sending bulk e-mails. ⚠**

Because `django-massmailer` intrinsically gives access to powerful features
(access to user data and sending e-mails in bulk) it is strongly recommended to
be as restrictive as possible when granting these permissions to prevent abuse
or spam.

### Query syntax

`django-massmailer` allows you to write queries in a domain-specific language
to select the users you want to reach. You can think of it as heavily
simplified SQL with a syntax that looks like filters in the Django ORM.

Here is a short demonstration of the syntax:

```python
SomeModel [as name]
  .field = 42
  (.field contains "string" or
   .field contains i"case insensitive")
  count(.related_field) > 10

alias some_name = .some_field
```

Filters are implicity joined by the and operator. If you are not querying on
the User model directly, you must create a user alias targeting a field
containing the related user.

### Templates

Templates use the [Jinja2 templating engine](http://jinja.pocoo.org/) to
generate the contents of the e-mails. The model selected in your query will be
passed directly in the context of the template, as well as the different
aliases that were defined in the query.

There are three templates you have to fill, one for the subject line, one for
the plaintext content, and optionally one for the HTML content. The HTML
template can also be generated directly from the plaintext e-mail.

Example:

```jinja
Greetings, {{ user.get_full_name().strip().title() }}!

{% if user.is_staff %}With great power comes great responsibility.{% endif %}
```

#### Template filters

In addition to the Jinja2 [builtin
filters](http://jinja.pocoo.org/docs/2.10/templates/#builtin-filters),
`django-massmailer` provides a few other convenience filters.

The following filters are directly passed to the [Babel functions of the same
name](http://babel.pocoo.org/en/latest/api/dates.html) using the locale set in
template:

- `format_date`: formats the date according to a given pattern.
- `format_time`: formats the time according to a given pattern.
- `format_datetime`: formats the datetime according to a given pattern.

Example:

```jinja
You have joined our website on {{ user.date_joined|format_date }}.
```

## Contributing

`django-massmailer` enforces various style constraints. You need to install
pre-commit hooks to make sure your commits respect them:

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Licence

`django-massmailer` is distributed under the GPLv3 licence.

- Copyright (C) 2016 Alexandre Macabies
- Copyright (C) 2016 Antoine Pietri

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
