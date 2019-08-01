import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, Client

from massmailer.models import Template, TemplateItem


def create_simple_template():
    return Template.objects.create(
        name="Much template",
        language="en-US",
        subject="{{ user.username }}, it's Christmas!",
        plain_body="Hi {{ user.username }}, today is {{ today|format_date }}.",
    )


def create_html_template():
    return Template.objects.create(
        name="Much HTML template",
        language="en-US",
        subject="{{ user.username }}, it's Christmas!",
        plain_body="Hi {{ user.username }}, today is {{ today|format_date }}.",
        html_body="<p>Hi {{ user.username }}, today is {{ today|format_date }}.</p>",
    )


def create_simple_baguette_template():
    return Template.objects.create(
        name="Très gabarit",
        language="fr",
        subject="{{ user.username }}, c'est Noël !",
        plain_body="Bonjour {{ user.username }}, on est le {{ today|format_date }}.",
    )


def create_altering_data_template():
    return Template.objects.create(
        name="I am the danger",
        language="en-us",
        subject="Test delete",
        plain_body="{{ user.delete() }}",
    )


class TemplateTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user("zopieux")
        self.client.force_login(self.user)

    @property
    def template_context(self):
        return {'user': self.user, 'today': datetime.date(2019, 12, 24)}

    def test_template_variables(self):
        t = create_simple_template()
        self.assertSetEqual(t.variables(TemplateItem.subject), {'user'})
        self.assertSetEqual(t.variables(TemplateItem.plain), {'user', 'today'})
        self.assertSetEqual(t.variables(TemplateItem.html), set())

    def test_template_html_enabled(self):
        t = create_simple_template()
        self.assertFalse(t.html_enabled)
        t = create_html_template()
        self.assertTrue(t.html_enabled)

    def test_template_preview(self):
        t = create_simple_template()
        self.assertEqual(
            t.subject_preview(),
            """<span class="placeholder">\u25cc</span>, it's Christmas!""",
        )

    def test_template_render(self):
        t = create_html_template()
        self.assertEqual(
            t.render(TemplateItem.subject, self.template_context),
            "zopieux, it's Christmas!",
        )
        self.assertEqual(
            t.render(TemplateItem.plain, self.template_context),
            "Hi zopieux, today is Tuesday, December 24, 2019.",
        )
        self.assertEqual(
            t.render(TemplateItem.html, self.template_context),
            "<p>Hi zopieux, today is Tuesday, December 24, 2019.</p>",
        )

    def test_template_render_localized(self):
        t = create_simple_baguette_template()
        self.assertEqual(
            t.render(TemplateItem.subject, self.template_context),
            "zopieux, c'est Noël !",
        )
        self.assertEqual(
            t.render(TemplateItem.plain, self.template_context),
            "Bonjour zopieux, on est le mardi 24 décembre 2019.",
        )

    def test_template_render_escaping(self):
        t = create_html_template()
        context = self.template_context.copy()
        context['user'].username = "<script>"

        self.assertEqual(
            t.render(TemplateItem.subject, context),
            "<script>, it's Christmas!",
        )
        self.assertEqual(
            t.render(TemplateItem.plain, context),
            "Hi <script>, today is Tuesday, December 24, 2019.",
        )
        self.assertEqual(
            t.render(TemplateItem.html, context),
            "<p>Hi &lt;script&gt;, today is Tuesday, December 24, 2019.</p>",
        )

    def test_template_full_preview_missing_variables(self):
        t = create_simple_template()
        incomplete_context = self.template_context.copy()
        incomplete_context.pop("user")

        result = t.full_preview(incomplete_context)

        self.assertEqual(result['subject']['error']['type'], "undefined")
        msg = result['subject']['error']['msg']
        self.assertIn("user", msg)
        self.assertIn("undefined", msg)

    def test_template_full_preview_syntax_error(self):
        t = create_simple_template()
        t.subject = "Hello {{ user.username"

        result = t.full_preview(self.template_context)
        self.assertEqual(result['subject']['error']['type'], "syntax")
        self.assertIn(
            "unexpected end of template", result['subject']['error']['msg']
        )

    def test_template_full_preview_context(self):
        t = create_simple_template()

        result = t.full_preview(self.template_context)
        self.assertSetEqual(
            set(result['subject']['context']['declared']),
            # "user" is consumed
            {'language', 'today'},
        )

        self.assertListEqual(result['subject']['context']['missing'], [])

    def test_sandbox_rejects_alter_data(self):
        t = create_altering_data_template()
        result = t.full_preview(self.template_context)
        self.assertIn(
            '<bound method Model.delete of <User: zopieux>> '
            'is not safely callable',
            result['plain']['error']['msg'],
        )
