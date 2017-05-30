from django.urls import reverse

from prologin import tests
from mailing import models


class ReportingTestCase(tests.WithStaffUserMixin, tests.WithSuperUserMixin, tests.WithContestantMixin, tests.ProloginTestCase):
    def setUp(self):
        super().setUp()
        self.plain_tpl = models.Template(
            name="New edition",
            subject="Hello {{ user.username }}, let's have fun with {{ edition }}",
            plain_body="""
Hey, you are {% if user.email.startswith('test') %}fake{% else %}real{% endif %}.
""".strip())
        self.html_tpl = models.Template(
            name="New edition HTML",
            subject=self.plain_tpl.subject,
            plain_body=self.plain_tpl.plain_body,
            html_body="""
Hey, you are {% if user.email.startswith('test') %}<em>fake</em>{% else %}<strong>real</strong>{% endif %}.
""".strip())

    def test_variables(self):
        self.assertSetEqual(self.plain_tpl.variables(models.TemplateItem.subject), {'user', 'edition'})
        self.assertSetEqual(self.html_tpl.variables(models.TemplateItem.subject), {'user', 'edition'})
        self.assertSetEqual(self.plain_tpl.variables(models.TemplateItem.plain), {'user'})
        self.assertSetEqual(self.plain_tpl.variables(models.TemplateItem.html), set())

    def test_basic_properties(self):
        self.assertFalse(self.plain_tpl.html_enabled)
        self.assertTrue(self.html_tpl.html_enabled)
        self.assertEqual(self.plain_tpl.template_source(models.TemplateItem.subject), self.plain_tpl.subject)

    def test_preview(self):
        self.assertEqual(
            self.plain_tpl.preview(models.TemplateItem.subject),
            "Hello {p}, let's have fun with {p}".format(p=models.VARIABLE_PLACEHOLDER))
        self.assertEqual(
            self.plain_tpl.preview(models.TemplateItem.plain),
            "Hey, you are {p}fake{p}real{p}.".format(p=models.VARIABLE_PLACEHOLDER))

    def test_full_preview(self):
        context = {'user': self.contestant}
        self.assertDictEqual(self.plain_tpl.full_preview(context), {
            'subject': {'error':  {'msg': "'edition' is undefined", 'type': 'undefined'}},
            'plain': {'content': "Hey, you are real.", 'context': {'declared': [], 'missing': []}},
            'html': {'content': '', 'context': {'declared': ['user'], 'missing': []}},
        })

    def test_render(self):
        context = {'user': self.contestant, 'edition': self.edition}
        self.html_tpl.plain_preview()
        self.assertEqual(
            self.plain_tpl.render(models.TemplateItem.subject, context),
            "Hello {c}, let's have fun with {e}".format(c=self.contestant.username, e=self.edition))
        self.assertHTMLEqual(
            self.html_tpl.render(models.TemplateItem.html, context),
            "Hey, you are <strong>real</strong>.")

    def test_permissions(self):
        with self.user_login(self.contestant):
            response = self.client.get(reverse('mailing:dashboard'))
            self.assertInvalidResponse(response)

        with self.user_login(self.staff_user):
            response = self.client.get(reverse('mailing:dashboard'))
            self.assertValidResponse(response)

        with self.user_login(self.staff_user):
            response = self.client.get(reverse('mailing:batch:new'))
            self.assertInvalidResponse(response)

        with self.user_login(self.super_user):
            response = self.client.get(reverse('mailing:batch:new'))
            self.assertValidResponse(response)

    def test_404(self):
        self.plain_tpl.save()
        self.plain_tpl.refresh_from_db()
        tpl_pk = self.plain_tpl.pk

        with self.user_login(self.super_user):
            self.assertInvalidResponse(self.client.get(reverse('mailing:template:update', args=[tpl_pk + 1])))
            self.assertValidResponse(self.client.get(reverse('mailing:template:update', args=[tpl_pk])))
