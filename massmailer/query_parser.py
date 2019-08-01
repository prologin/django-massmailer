import ast
import functools
import itertools
import operator
import re

import pyparsing as p

from django.apps import apps
from django.db import models
from django.db.models import Q


class ParseError(ValueError):
    pass


class CaseInsensitive(str):
    pass


class ParseResult:
    queryset = None
    model_name = None
    aliases = {}


def _find_subclasses(cls):
    found = {}
    subclasses = cls.__subclasses__()
    if subclasses:
        for sub_cls in subclasses:
            found.update(_find_subclasses(sub_cls))
    elif not cls.__name__.startswith('_'):
        found[cls.__name__.lower()] = cls
    return found


class QueryParser:
    """
    A parser for a simple grammar to write user-friendly queries that get
    translated to Django ORM.

    Aggregate functions such as count() shall be registered in the
    available_funcs mapping:
        func name → func
    Use load_django_funcs=True to load all known Django ORM functions.

    Available Django models shall be registered in the available_models
    mapping:
        model name → model class
    Use load_django_models=True to load all known Django models for the current
    project.

    There also is a concept of literal enums that have to be registered in the
    available_enums mapping:
        (enum name eg. 'Namespace.EnumName') → enum class
    where 'enum class' shall implement Python's enum.Enum API, ie.
    EnumCls[name] and EnumCls(value) methods.

    Syntax example:

        # this is a comment
        SomeModel [as name]
          .field = 42
          # two field predicates are joined with "and" if not explicitly using
          # "or"
          count(.related_field) > 10
          # function arguments are supported:
          substr(.field, 3, 4) = "brut"
          # there is a support for literal enums, that get replaced with their
          # value
          .field = SomeClass.SomeEnum.some_enum_member
          (.field contains "string" or
           .field contains i"case insensitive")

        alias some_name = .some_field
    """

    def __init__(
        self, load_django_funcs=True, load_django_models=True, load_enums=True
    ):
        self.available_funcs = {}
        self.available_models = {}
        self.available_enums = {}

        if load_django_funcs:
            self.available_funcs.update(_find_subclasses(models.Func))

        if load_django_models:
            self.available_models.update(
                {model.__name__: model for model in apps.get_models()}
            )

        if load_enums:
            from massmailer import REGISTERED_ENUMS

            self.available_enums.update(REGISTERED_ENUMS)

    def parse_query(self, query: str) -> ParseResult:
        func_name_gen = itertools.count(0)

        def parse_enum(tokens):
            enum, member = tokens[0].rsplit('.', 1)
            try:
                enum = self.available_enums[enum]
            except KeyError:
                raise ParseError(
                    "Unknown enum '{}'.\n\nAvailable enums: {}".format(
                        enum, ', '.join(self.available_enums.keys())
                    )
                )
            try:
                # try with member name
                member = enum[member]
            except KeyError:
                # try with member value
                try:
                    member = enum(member)
                except ValueError:
                    raise ParseError(
                        "Invalid member '{}' of {}".format(member, enum)
                    )
            return member.value

        def parse_string(tokens):
            string = tokens[0]['string']
            if tokens[0].get('nocase'):
                return CaseInsensitive(string)
            return string

        def parse_field(tokens):
            return '__'.join(tokens)

        def generic_negate(t):
            return t.get('negate') is True

        def generic_value(t):
            return t.get('value')

        def field_value(field_getter, value_getter, negate_getter=None):
            """
            Generic parser for <field> <op> <value> that builds Q(field=value).

            Supports function calls on the field, ie. func(<field>) <op> <value>
                that returns Q(func_result=value) and annotates the query with
                func_result=<func>(<field>).

            'field_getter' is invoked with the tokens as param 0 and shall
                return a format-string in which {} will be replaced with the
                field name.

            'value_getter' is invoked with the tokens as param 0 and shall
                return the value.

            If 'negate_getter' is defined, it is invoked with the tokens as
                param 0. If the return value is True, then the returned queryset
                is negated (~q).

            Returns (queryset: Q, annotations: dict).
            """

            def parse(tokens):
                t = tokens[0]
                annotations = {}
                field_name = t.get('field')
                func_call = t.get('func_call')
                field_format = field_getter(t)

                if func_call is not None:
                    field_name = f'func_{next(func_name_gen)}'
                    annotations[field_name] = func_call

                q = Q(**{field_format.format(field_name): value_getter(t)})

                if negate_getter is not None and negate_getter(t):
                    q = ~q

                return q, annotations

            return parse

        def unsupported(name):
            def defaulter(value):
                raise NotImplementedError(
                    f"'{name} <{type(value)}>' is unsupported"
                )

            return defaulter

        def generic_suffix(suffix):
            def get_field(t):
                return '{}__' + suffix

            return field_value(get_field, generic_value)

        def generic_case_insensitive_suffix(orm_suffix, defaulter):
            """
            Field getter for Django ORM case-insensitive suffixes. Returns a
            formatter that uses 'orm_suffix' if the value is a normal string,
            otherwise returns a formatter with 'i' before 'orm_suffix'.

            If the value is neither a string nor a case-insensitive string,
            returns defaulter(value).
            """

            def get_field(t):
                value = t.get('value')
                if isinstance(value, CaseInsensitive):
                    return '{}__i' + orm_suffix
                elif isinstance(value, str):
                    return '{}__' + orm_suffix

                return defaulter(value)

            return get_field

        def parse_equality():
            def field_defaulter(value):
                # other types just need a standard equality
                return '{}'

            return field_value(
                generic_case_insensitive_suffix('exact', field_defaulter),
                generic_value,
            )

        def parse_contains():
            return field_value(
                generic_case_insensitive_suffix(
                    'contains', unsupported('contains')
                ),
                generic_value,
                generic_negate,
            )

        def parse_match():
            return field_value(
                generic_case_insensitive_suffix('regex', unsupported('match')),
                generic_value,
                generic_negate,
            )

        def parse_startswith():
            return field_value(
                generic_case_insensitive_suffix(
                    'startswith', unsupported('starts with')
                ),
                generic_value,
                generic_negate,
            )

        def parse_endswith():
            return field_value(
                generic_case_insensitive_suffix(
                    'endswith', unsupported('ends with')
                ),
                generic_value,
                generic_negate,
            )

        def parse_inequality(tokens):
            q, annotations = parse_equality()(tokens)
            return ~q, annotations

        def parse_between():
            def get_field(t):
                return '{}__range'

            def get_value(t):
                return t.get('min'), t.get('max')

            return field_value(get_field, get_value, generic_negate)

        def parse_is_null():
            def get_field(t):
                return '{}__isnull'

            def get_value(t):
                return True

            return field_value(get_field, get_value, generic_negate)

        def parse_is_empty():
            def get_field(t):
                return '{}__exact'

            def get_value(t):
                return ""

            return field_value(get_field, get_value, generic_negate)

        def parse_func_call(tokens):
            name = tokens.get('func_name')
            field = tokens.get('func_field')
            args = tokens.get('func_args', ())
            return self.available_funcs[name](field, *args)

        def parse_model(tokens):
            return self.available_models[tokens['model']]

        def parse_not(tokens):
            query, annotations = tokens[0][0]
            return ~query, annotations

        def generic_annotated_op(op):
            def reducer(a, b):
                query_a, annotations_a = a
                query_b, annotations_b = b
                return op(query_a, query_b), {**annotations_a, **annotations_b}

            return reducer

        def parse_and(tokens):
            parts = tokens[0]
            return functools.reduce(generic_annotated_op(operator.iand), parts)

        def parse_or(tokens):
            parts = tokens[0]
            return functools.reduce(generic_annotated_op(operator.ior), parts)

        def parse(tokens):
            q, annotations = tokens.get('filter', (Q(), {}))
            model = tokens['model']
            model_name = model._meta.model_name
            qs = model._default_manager.annotate(**annotations).filter(q)
            custom_model_name = tokens.get('model_name')
            if custom_model_name:
                model_name = custom_model_name[0]
            result = ParseResult()
            result.queryset = qs
            result.model_name = model_name
            result.aliases = {
                name: field for name, field in tokens.get('aliases', [])
            }
            result.aliases.pop(model_name, None)
            return result

        # The grammar
        G = p.Group
        comments = p.Suppress(p.ZeroOrMore(p.pythonStyleComment))
        point = p.Literal('.')
        expo = p.CaselessLiteral('e')
        plusorminus = p.Literal('+') | p.Literal('-')
        number = p.Word(p.nums)
        integer = p.Combine(p.Optional(plusorminus) + number)
        floatnumber = p.Combine(
            integer
            + p.Optional(point + p.Optional(number))
            + p.Optional(expo + integer)
        )
        hexnumber = p.Combine(
            p.Optional(plusorminus)
            + p.CaselessLiteral('0x')
            + p.Word(p.hexnums)
        )
        numscalar = (hexnumber | floatnumber | integer).setParseAction(
            lambda t: ast.literal_eval(t[0])
        )
        boolean = (p.Keyword('true') | p.Keyword('false')).setParseAction(
            lambda t: t[0].lower() == 'true'
        )
        alpha_under = p.Regex(r'[a-z][a-z0-9]*(_[a-z0-9]+)*', re.I)
        enumvalue = p.Combine(
            alpha_under + '.' + alpha_under + '.' + alpha_under
        ).setParseAction(parse_enum)
        string = G(
            p.Optional(p.Literal('i'))('nocase')
            + p.quotedString.setParseAction(p.removeQuotes)('string')
        ).setParseAction(parse_string)
        value = (string | numscalar | boolean | enumvalue).setParseAction(
            lambda t: t[0]
        )('value')
        model = p.Regex(r'([A-Z][a-z0-9]*)+').setParseAction(parse_model)(
            'model'
        )
        field_name = p.OneOrMore(p.Suppress('.') + alpha_under).setParseAction(
            parse_field
        )('field')
        func_call = (
            p.Word(p.alphas)('func_name')
            + p.Suppress('(')
            + field_name('func_field')
            + p.Optional(p.Suppress(',') + p.delimitedList(value))('func_args')
            + p.Suppress(')')
        ).setParseAction(parse_func_call)('func_call')
        field = field_name | func_call
        is_kw = p.Suppress(p.Keyword('is'))
        negation = p.Optional(p.Keyword('not')).setParseAction(
            lambda t: bool(t)
        )('negate')
        negation_does = p.Optional(
            p.Keyword("doesn't") | p.Keyword("does not")
        ).setParseAction(lambda t: bool(t))('negate')
        equality = G(field + p.Suppress('=') + value).setParseAction(
            parse_equality()
        )
        inequality = G(field + p.Suppress('!=') + value).setParseAction(
            parse_inequality
        )
        lt = G(field + p.Suppress('<') + value).setParseAction(
            generic_suffix('lt')
        )
        lte = G(field + p.Suppress('<=') + value).setParseAction(
            generic_suffix('lte')
        )
        gt = G(field + p.Suppress('>') + value).setParseAction(
            generic_suffix('gt')
        )
        gte = G(field + p.Suppress('>=') + value).setParseAction(
            generic_suffix('gte')
        )
        null_or_none = p.Keyword('null') | p.Keyword('none')
        null = G(field + is_kw + negation + null_or_none).setParseAction(
            parse_is_null()
        )
        empty = G(
            field + is_kw + negation + p.Keyword('empty')
        ).setParseAction(parse_is_empty())
        contains = G(
            field
            + negation_does
            + p.Suppress(p.Keyword('contain') | p.Keyword('contains'))
            + string('value')
        ).setParseAction(parse_contains())
        startswith = G(
            field
            + negation_does
            + p.Suppress(p.Keyword('start with') | p.Keyword('starts with'))
            + string('value')
        ).setParseAction(parse_startswith())
        endswith = G(
            field
            + negation_does
            + p.Suppress(p.Keyword('end with') | p.Keyword('ends with'))
            + string('value')
        ).setParseAction(parse_endswith())
        matches = G(
            field
            + negation_does
            + p.Suppress(p.Keyword('match') | p.Keyword('matches'))
            + string('value')
        ).setParseAction(parse_match())
        between = G(
            field
            + negation
            + p.Suppress(p.Keyword('between'))
            + value('min')
            + p.Suppress(p.Keyword('and'))
            + value('max')
        ).setParseAction(parse_between())

        clause = (
            equality
            | inequality
            | lte
            | gte
            | lt
            | gt
            | between
            | null
            | empty
            | contains
            | startswith
            | endswith
            | matches
        )

        c_not = (p.Suppress(p.Keyword('not')), 1, p.opAssoc.RIGHT, parse_not)
        c_or = (p.Suppress(p.Keyword('or')), 2, p.opAssoc.LEFT, parse_or)
        c_and = (
            p.Suppress(p.Optional(p.Keyword('and'), default=p.Keyword('and'))),
            2,
            p.opAssoc.LEFT,
            parse_and,
        )

        filter = p.infixNotation(clause + comments, [c_not, c_or, c_and])

        alias = (
            p.Keyword('alias')
            + alpha_under('name')
            + p.Optional(p.Suppress('=') + field_name('field'))
            + comments
        ).setParseAction(lambda t: (t['name'], t.get('field', t['name'])))

        stmt = (
            p.stringStart()
            + comments
            + model
            + p.Optional((p.Suppress(p.Keyword('as')) + alpha_under))(
                'model_name'
            )
            + comments
            + p.Optional(filter)('filter')
            + comments
            + p.ZeroOrMore(alias)('aliases')
            + comments
            + p.StringEnd()
        ).setParseAction(parse)

        return stmt.parseString(query)[0]
