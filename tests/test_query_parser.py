import unittest

from django.test import TestCase

from massmailer.query_parser import QueryParser


class QueryParserTestCase(TestCase):
    def setUp(self):
        from tests.models import SomeModel, SomeChild

        foo = SomeModel.objects.create(
            text_field="foo", int_field=42, bool_field=True
        )
        SomeChild.objects.create(parent=foo, child_field="child1")
        SomeChild.objects.create(parent=foo, child_field="child2")

        SomeModel.objects.create(
            text_field="BAROO", int_field=1337, bool_field=False
        )

    def test_django_manual_registry(self):
        qp = QueryParser(load_django_funcs=False, load_django_models=False)
        self.assertNotIn('SomeModel', qp.available_models)

    def test_django_func_registry(self):
        qp = QueryParser(load_django_models=False)
        self.assertIn('count', qp.available_funcs)
        self.assertIn('avg', qp.available_funcs)
        self.assertIn('min', qp.available_funcs)
        self.assertIn('max', qp.available_funcs)

    def test_django_models_loaded(self):
        from tests.models import SomeModel

        qp = QueryParser(load_django_funcs=False)
        self.assertIn('SomeModel', qp.available_models)
        self.assertIs(qp.available_models['SomeModel'], SomeModel)

    def test_query_with_model(self):
        qp = QueryParser(load_django_funcs=False)

        with self.assertRaisesMessage(KeyError, 'Garbage'):
            qp.parse_query('Garbage as foo')

        qp.parse_query('SomeModel as foo')

    def test_query_comment(self):
        qp = QueryParser(load_django_funcs=False)
        qp.parse_query("# a comment\nSomeModel")

    def test_query_text_field_predicate(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field = 'foo'")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, 'foo')

    def test_query_int_field_predicate(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .int_field = 42")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 42)

    def test_query_bool_field_predicate(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .bool_field = true")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().bool_field, True)
        r = qp.parse_query("SomeModel .bool_field = false")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().bool_field, False)

    # SQLite doesn't support case-sensitive LIKE :-(
    @unittest.expectedFailure
    def test_query_contains_cs_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field contains 'oo'")
        self.assertEqual(r.queryset.count(), 1)

    def test_query_contains_ci_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field contains i'oo'")
        self.assertEqual(r.queryset.count(), 2)

    def test_query_between_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .int_field between 42 and 50")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field between 0 and 41")
        self.assertEqual(r.queryset.count(), 0)

    def test_query_and_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .int_field = 42 .text_field = 'foo'")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel .int_field = 42 .text_field = 'not foo'")
        self.assertEqual(r.queryset.count(), 0)

    def test_query_or_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query(
            "SomeModel .int_field = 42 or .text_field = 'BAROO'"
        )
        self.assertEqual(r.queryset.count(), 2)

    def test_query_model_alias(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel")
        self.assertEqual(r.model_name, 'somemodel')

        r = qp.parse_query("SomeModel as meh")
        self.assertEqual(r.model_name, 'meh')

    def test_query_aliases(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel")
        self.assertDictEqual(r.aliases, {})

        r = qp.parse_query("SomeModel alias enfants = .children")
        self.assertDictEqual(r.aliases, {'enfants': 'children'})

    def test_query_func_count(self):
        qp = QueryParser()
        r = qp.parse_query("SomeModel count(.children) = 0")
        self.assertEqual(r.queryset.first().text_field, 'BAROO')

        r = qp.parse_query("SomeModel count(.children) = 1")
        self.assertEqual(r.queryset.count(), 0)

        r = qp.parse_query("SomeModel count(.children) = 2")
        self.assertEqual(r.queryset.first().text_field, 'foo')

        with self.assertRaisesMessage(Exception, 'garbage'):
            qp.parse_query("SomeModel garbage(.text_field) = 1")

    def test_query_enum(self):
        from tests.models import SomeEnum

        qp = QueryParser()
        # Register the enum
        qp.available_enums['MyApp.SomeEnum'] = SomeEnum

        r = qp.parse_query("SomeModel .int_field = MyApp.SomeEnum.foo")
        self.assertEqual(r.queryset.first().int_field, SomeEnum.foo.value)

        r = qp.parse_query("SomeModel .text_field = MyApp.SomeEnum.bar")
        self.assertEqual(r.queryset.first().text_field, SomeEnum.bar.value)

        with self.assertRaisesMessage(Exception, 'unknown enum'):
            qp.parse_query("SomeModel .text_field = Not.Even.close")
