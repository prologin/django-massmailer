import ast
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
        func_i = 0

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
                        "invalid member '{}' of {}".format(member, enum)
                    )
            return member.value

        def parse_string(tokens):
            string = tokens['string']
            if tokens.get('nocase'):
                return CaseInsensitive(string)
            return string

        def parse_field(tokens):
            return '__'.join(tokens)

        def parse_clause(tokens):
            nonlocal func_i
            annotations = {}
            field = tokens.get('field')
            value = tokens.get('value')
            negation = tokens.get('negation', False)
            insensitive = isinstance(value, CaseInsensitive)

            if tokens.get('operation'):
                func = self.available_funcs[tokens['func_name']]
                name = 'func_{}'.format(func_i)
                func_i += 1
                annotations[name] = func(tokens['func_field'])
                field = name

            if tokens.get('='):
                if insensitive:
                    field += '__iexact'
            elif tokens.get('!='):
                negation = True
            elif tokens.get('<='):
                field += '__lte'
            elif tokens.get('>='):
                field += '__gte'
            elif tokens.get('<'):
                field += '__lt'
            elif tokens.get('>'):
                field += '__gt'
            elif tokens.get('empty'):
                value = ''
            elif tokens.get('null'):
                field += '__isnull'
                value = not negation
                negation = False
            elif tokens.get('contains'):
                if insensitive:
                    field += '__icontains'
                else:
                    field += '__contains'
            elif tokens.get('startswith'):
                if insensitive:
                    field += '__istartswith'
                else:
                    field += '__startswith'
            elif tokens.get('endswith'):
                if insensitive:
                    field += '__iendswith'
                else:
                    field += '__endswith'
            elif tokens.get('matches'):
                if insensitive:
                    field += '__iregex'
                else:
                    field += '__regex'
            elif tokens.get('between'):
                field += '__range'
                value = (tokens['min'], tokens['max'])
            else:
                raise ParseError("unknown clause token {}".format(tokens))

            q = Q(**{field: value})
            if negation:
                q = ~q
            return q, annotations

        def parse_filter(tokens):
            query = Q()
            annotations = {}
            operation = 'and'
            negation = False
            for token in tokens:
                if isinstance(token, p.ParseResults):
                    q, ann = parse_filter(token)
                    query &= q
                    annotations.update(ann)
                elif isinstance(token, str):
                    if token in ('or', 'and'):
                        operation = token
                    elif token == 'not':
                        negation = True
                else:
                    q, ann = token
                    annotations.update(ann)
                    if negation:
                        q = ~q
                    if operation == 'or':
                        query |= q
                    else:
                        query &= q
            return query, annotations

        def parse_model(tokens):
            return self.available_models[tokens['model']]

        def parse(tokens):
            query, annotations = tokens.get('filter', (Q(), {}))
            model = tokens['model']
            model_name = model._meta.model_name
            qs = model._default_manager.annotate(**annotations).filter(query)
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
        # TODO: implement operation args eg. substr(.field, 1, 5)
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
        string = (
            p.Optional(p.Literal('i')).setResultsName('nocase')
            + p.quotedString.setParseAction(p.removeQuotes).setResultsName(
                'string'
            )
        ).setParseAction(parse_string)
        value = (
            (string | numscalar | boolean | enumvalue)
            .setResultsName('value')
            .setParseAction(lambda t: t[0])
        )
        model = (
            p.Regex(r'([A-Z][a-z0-9]*)+')
            .setParseAction(parse_model)
            .setResultsName('model')
        )
        field_name = (
            p.OneOrMore(p.Suppress('.') + alpha_under)
            .setParseAction(parse_field)
            .setResultsName('field')
        )
        operation = (
            p.Word(p.alphas).setResultsName('func_name')
            + p.Suppress('(')
            + field_name.setResultsName('func_field')
            + p.Suppress(')')
        ).setResultsName('operation')
        field = field_name | operation
        is_kw = p.Keyword('is')
        negation = (
            p.Optional(p.Keyword('not'))
            .setParseAction(lambda t: bool(t))
            .setResultsName('negation')
        )
        negation_does = (
            p.Optional(p.Keyword("doesn't") | p.Keyword("does not"))
            .setParseAction(lambda t: bool(t))
            .setResultsName('negation')
        )
        equality = (field + p.Suppress('=') + value).setResultsName('=')
        inequality = (field + p.Suppress('!=') + value).setResultsName('!=')
        lt = (field + p.Suppress('<') + value).setResultsName('<')
        lte = (field + p.Suppress('<=') + value).setResultsName('<=')
        gt = (field + p.Suppress('>') + value).setResultsName('>')
        gte = (field + p.Suppress('>=') + value).setResultsName('>=')
        null_or_none = p.Keyword('null') | p.Keyword('none')
        null = (field + is_kw + negation + null_or_none).setResultsName('null')
        empty = (field + is_kw + negation + p.Keyword('empty')).setResultsName(
            'empty'
        )
        contains = (
            field
            + negation_does
            + (p.Keyword('contain') | p.Keyword('contains'))
            + string.setResultsName('value')
        ).setResultsName('contains')
        startswith = (
            field
            + negation_does
            + (p.Keyword('start with') | p.Keyword('starts with'))
            + string.setResultsName('value')
        ).setResultsName('startswith')
        endswith = (
            field
            + negation_does
            + (p.Keyword('end with') | p.Keyword('ends with'))
            + string.setResultsName('value')
        ).setResultsName('endswith')
        matches = (
            field
            + negation_does
            + (p.Keyword('match') | p.Keyword('matches'))
            + string.setResultsName('value')
        ).setResultsName('matches')
        between = (
            field
            + negation
            + p.Keyword('between')
            + value.setResultsName('min')
            + p.Keyword('and')
            + value.setResultsName('max')
        ).setResultsName('between')
        clause = (
            (
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
            .setParseAction(parse_clause)
            .setResultsName('comparison')
        )
        oper_not = p.Keyword('not')
        oper_and = p.Keyword('and')
        oper_or = p.Keyword('or')
        filter = p.operatorPrecedence(
            clause + comments,
            [
                (oper_not, 1, p.opAssoc.RIGHT),
                (oper_or, 2, p.opAssoc.LEFT),
                (p.Optional(oper_and, default='and'), 2, p.opAssoc.LEFT),
            ],
        ).setParseAction(parse_filter)
        alias = (
            p.Keyword('alias')
            + alpha_under.setResultsName('name')
            + p.Optional(p.Suppress('=') + field_name.setResultsName('field'))
            + comments
        ).setParseAction(lambda t: (t['name'], t.get('field', t['name'])))
        stmt = (
            p.stringStart()
            + comments
            + model
            + p.Optional(
                (p.Suppress(p.Keyword('as')) + alpha_under)
            ).setResultsName('model_name')
            + comments
            + p.Optional(filter).setResultsName('filter')
            + comments
            + p.ZeroOrMore(alias).setResultsName('aliases')
            + comments
            + p.StringEnd()
        ).setParseAction(parse)

        return stmt.parseString(query)[0]


def parse_query(query: str) -> ParseResult:
    return QueryParser().parse_query(query)
