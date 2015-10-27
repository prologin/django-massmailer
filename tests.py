import prologin.tests
from mailing.models import MailingTemplate, TemplateItem


class ReportingTestCase(prologin.tests.ProloginTestCase):
    def setUp(self):
        super().setUp()
        self.tpl = MailingTemplate('new-edition')

    def test_variables(self):
        print(self.tpl.variables(TemplateItem.subject))
        print(self.tpl.variables(TemplateItem.plain))
