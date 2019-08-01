import unittest

from django.test import TestCase

from massmailer.query_parser import QueryParser, ParseError


class QueryParserTestCase(TestCase):
    def setUp(self):
        from tests.models import SomeModel, SomeChild

        foo = SomeModel.objects.create(
            text_field="foo", int_field=42, bool_field=True, other_text="foo"
        )
        SomeChild.objects.create(parent=foo, child_field="child1")
        SomeChild.objects.create(parent=foo, child_field="child2")

        SomeModel.objects.create(
            text_field="BAROO", int_field=1337, bool_field=False
        )

        SomeModel.objects.create(
            text_field="coq", int_field=3, bool_field=None, other_text="quxcoq"
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

    def test_query_no_such_model(self):
        qp = QueryParser(load_django_funcs=False)
        with self.assertRaisesRegex(ParseError, 'Unknown.+model.+Garbage'):
            qp.parse_query("Garbage")

    def test_query_simple(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel")
        self.assertEqual(r.queryset.count(), 3)

    def test_query_comment(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("# a comment\nSomeModel")
        self.assertEqual(r.queryset.count(), 3)

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

        r = qp.parse_query("SomeModel .bool_field = False")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().bool_field, False)

    def test_query_negation(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel not .int_field = 42")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel not not .int_field = 42")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel not not not .int_field = 42")
        self.assertEqual(r.queryset.count(), 2)

    # SQLite doesn't support case-sensitive LIKE :-(
    @unittest.expectedFailure
    def test_query_contains_cs_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field contains 'oo'")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel .text_field does not contain 'oo'")
        self.assertEqual(r.queryset.count(), 2)

    def test_query_contains_ci_filter(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field contains i'oo'")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .text_field does not contain i'oo'")
        self.assertEqual(r.queryset.count(), 1)

    def test_query_between_filter(self):
        qp = QueryParser()
        r = qp.parse_query("SomeModel .int_field between 42 and 50")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field between 0 and 41")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel count(.children) between -1 and 1")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .int_field not between 42 and 1337")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 3)

        # with self.assertRaises(TypeError, "'between' does not support"):
        qp.parse_query("SomeModel .int_field between true and false")

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

    def test_query_arithmetic(self):
        qp = QueryParser()
        r = qp.parse_query("SomeModel .int_field = 0b101010")
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field = 0x2a")
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field = 0o52")
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field = -(-4.2e1)")
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query("SomeModel .int_field = (20 * 2**2 / 2) + 4 - 2")
        self.assertEqual(r.queryset.first().int_field, 42)

        r = qp.parse_query(
            "SomeModel .other_text = concat('qux', .text_field)"
        )
        self.assertEqual(r.queryset.first().other_text, "quxcoq")

    def test_query_comparators(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .int_field > 42")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel .int_field >= 42")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .int_field < 1337")
        self.assertEqual(r.queryset.count(), 2)
        self.assertEqual(r.queryset.first().text_field, "foo")

        r = qp.parse_query("SomeModel .int_field <= 1337")
        self.assertEqual(r.queryset.count(), 3)

        r = qp.parse_query("SomeModel .int_field != 3")
        self.assertEqual(r.queryset.count(), 2)

    def test_query_null_empty(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .bool_field is null")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, "coq")

        r = qp.parse_query("SomeModel .bool_field is not null")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .other_text is empty")
        self.assertEqual(r.queryset.count(), 1)

        r = qp.parse_query("SomeModel .text_field is not empty")
        self.assertEqual(r.queryset.count(), 3)

    def test_query_starts_with(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field starts with 'bar'")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, "BAROO")

        r = qp.parse_query("SomeModel .text_field does not start with 'bar'")
        self.assertEqual(r.queryset.count(), 2)

    def test_query_ends_with(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field end with 'oo'")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .text_field does not end with 'oo'")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 3)

    def test_query_matches(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field matches '[oO]{2}'")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel .text_field does not match '[oO]{2}'")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, 3)

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

    def test_query_field_as_value(self):
        qp = QueryParser(load_django_funcs=False)
        r = qp.parse_query("SomeModel .text_field = .other_text")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, "foo")

    def test_query_func_count(self):
        qp = QueryParser()
        r = qp.parse_query("SomeModel count(.children) = 0")
        self.assertEqual(r.queryset.count(), 2)

        r = qp.parse_query("SomeModel count(.children) = 1")
        self.assertEqual(r.queryset.count(), 0)

        r = qp.parse_query("SomeModel count(.children) = 2")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, 'foo')

    def test_query_no_such_func(self):
        qp = QueryParser(load_django_funcs=False)
        with self.assertRaisesRegex(ParseError, r'Unknown.+garbage'):
            qp.parse_query("SomeModel garbage(.text_field) = 1")

    def test_query_func_substr(self):
        qp = QueryParser()
        r = qp.parse_query("SomeModel substr(.text_field, 1, 2) = 'fo'")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, 'foo')

        r = qp.parse_query("SomeModel length(.text_field) = .int_field")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, 'coq')

    def test_query_enum(self):
        from tests.models import SomeEnum

        qp = QueryParser(load_django_funcs=False)
        # Register the enum
        qp.available_enums['MyApp.SomeEnum'] = SomeEnum

        r = qp.parse_query("SomeModel .int_field = MyApp.SomeEnum.foo")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().int_field, SomeEnum.foo.value)

        r = qp.parse_query("SomeModel .text_field = MyApp.SomeEnum.bar")
        self.assertEqual(r.queryset.count(), 1)
        self.assertEqual(r.queryset.first().text_field, SomeEnum.bar.value)

    def test_query_no_such_enum(self):
        qp = QueryParser(load_django_funcs=False)

        with self.assertRaisesRegex(ParseError, r"Unknown.+Do\.Not"):
            qp.parse_query("SomeModel .text_field = Do.Not.Exists")

    def test_query_no_such_enum_member(self):
        from tests.models import SomeEnum

        qp = QueryParser(load_django_funcs=False)
        # Register the enum
        qp.available_enums['MyApp.SomeEnum'] = SomeEnum

        with self.assertRaisesRegex(
            ParseError, r"SomeEnum.+no member.+garbage"
        ):
            qp.parse_query("SomeModel .text_field = MyApp.SomeEnum.garbage")
