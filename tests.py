from django.urls import reverse
from unittest import mock

from prologin import tests
from mailing import models, forms


class TemplateTestCase(tests.WithContestantMixin, tests.ProloginTestCase):
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
            'subject': {'error': {'msg': "'edition' is undefined", 'type': 'undefined'}},
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


class PermissionTestCase(tests.WithStaffUserMixin, tests.WithSuperUserMixin, tests.WithContestantMixin,
                         tests.ProloginTestCase):
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
        tpl = models.Template(name="foo")
        tpl.save()

        with self.user_login(self.super_user):
            self.assertInvalidResponse(self.client.get(reverse('mailing:template:update', args=[tpl.pk + 1])))
            self.assertValidResponse(self.client.get(reverse('mailing:template:update', args=[tpl.pk])))


class BatchSendTestCase(tests.WithSuperUserMixin, tests.ProloginTestCase):
    @mock.patch('mailing.tasks.send_email')
    def test_send(self, send_email):
        def mark_mail_as_sent(args, **kwargs):
            # simulate celery sending the mail
            pk, = args
            email = models.BatchEmail.objects.get(pk=pk)
            email.state = models.MailState.sent.value
            email.save()

        send_email.apply_async = mock.MagicMock()
        send_email.apply_async.side_effect = mark_mail_as_sent

        template = models.Template(
            name="such template",
            subject="salut {{ user }}",
            plain_body="salut toi",
        )
        template.save()
        query = models.Query(
            name="much query",
            query="ProloginUser as user",
        )
        query.save()

        with self.user_login(self.super_user):
            data = {'name': "this is my test batch", 'template': template.pk, 'query': query.pk}
            # first send: should be greeted with "foolproof is required"
            response = self.client.post(reverse('mailing:batch:new'), data)
            self.assertFormError(response, 'form', 'foolproof', "This field is required.")
            # next send: should be ok
            data['foolproof'] = forms.CreateBatchForm.FOOLPROOF_PHRASE % {'n': 1}
            response = self.client.post(reverse('mailing:batch:new'), data, follow=True)

        self.assertValidResponse(response)
        content = response.content.decode()
        subject = template.render(models.TemplateItem.subject, {'user': self.super_user.username})
        self.assertIn(data['name'], content)
        self.assertIn(self.super_user.username, content)
        self.assertIn(template.name, content)
        self.assertIn(query.name, content)
        self.assertIn(subject, content)

        # are all mail sent?
        self.assertTrue(models.Batch.objects.get().completed)
