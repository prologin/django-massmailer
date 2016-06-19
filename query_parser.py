from django.apps import apps
from django.db.models import Func
from django.db.models import Q
from prologin.models import BaseEnumField
import ast
import pyparsing as p


class CaseInsensitive(str):
    pass


def find_funcs(cls):
    found = {}
    subclasses = cls.__subclasses__()
    if subclasses:
        for sub_cls in subclasses:
            found.update(find_funcs(sub_cls))
    elif not cls.__name__.startswith('_'):
        found[cls.__name__.lower()] = cls
    return found


class LazyEnums:
    enums = {}

    def __getitem__(self, item):
        if not self.enums:
            self.enums = {'{}.{}'.format(model.__name__, field._enum.__name__): field._enum
                          for model in apps.get_models()
                          for field in model._meta.fields if isinstance(field, BaseEnumField)}
        return self.enums[item]


available_funcs = find_funcs(Func)
available_enums = LazyEnums()


def parse_query(query, fallback_model=None):
    func_i = 0

    def parse_enum(tokens):
        enum, member = tokens[0].rsplit('.', 1)
        try:
            enum = available_enums[enum]
        except KeyError:
            raise SyntaxError("unknown enum '{}'".format(enum))
        try:
            # try with member name
            member = enum[member]
        except KeyError:
            # try with member value
            try:
                member = enum(member)
            except ValueError:
                raise SyntaxError("invalid member '{}' of {}".format(member, enum))
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
            func = available_funcs[tokens['func_name']]
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
            raise SyntaxError("unknown clause token {}".format(tokens))

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
                    raise SyntaxError("unknown op {}".format(token))
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
        return {model.__name__: model for model in apps.get_models()}[tokens['model']]

    def parse(tokens):
        query, annotations = tokens.get('filter', (Q(), {}))
        qs = tokens['model']._default_manager.annotate(**annotations).filter(query)
        using = tokens.get('using')
        if using:
            if not fallback_model:
                raise ValueError("`fallback_model` must be defined to use `using`")
            qs = fallback_model._default_manager.filter(pk__in=qs.values_list(using, flat=True))
        return qs

    # The grammar
    # TODO: implement operation args eg. substr(.field, 1, 5)
    point = p.Literal('.')
    expo = p.CaselessLiteral('e')
    plusorminus = p.Literal('+') | p.Literal('-')
    number = p.Word(p.nums)
    integer = p.Combine(p.Optional(plusorminus) + number)
    floatnumber = p.Combine(integer +
                            p.Optional(point + p.Optional(number)) +
                            p.Optional(expo + integer))
    hexnumber = p.Combine(p.Optional(plusorminus) + p.CaselessLiteral('0x') + p.Word(p.hexnums))
    numscalar = (hexnumber | floatnumber | integer).setParseAction(lambda t: ast.literal_eval(t[0]))
    boolean = (p.Keyword('true') | p.Keyword('false')).setParseAction(lambda t: t[0].lower() == 'true')
    alpha_under = p.Word(p.alphanums + '_')
    enumvalue = p.Combine(alpha_under + '.' + alpha_under + '.' + alpha_under).setParseAction(parse_enum)
    string = (p.Optional(p.Literal('i')).setResultsName('nocase') +
              p.quotedString.setParseAction(p.removeQuotes).setResultsName('string')).setParseAction(parse_string)
    value = ((string | numscalar | boolean | enumvalue)
             .setResultsName('value'))
    model = p.Regex(r'([A-Z][a-z0-9]*)+').setParseAction(parse_model).setResultsName('model')
    field_name = (p.OneOrMore(p.Suppress('.') + p.Regex(r'[a-zA-Z]+(_[a-zA-Z0-9]+)*'))
                  .setParseAction(parse_field).setResultsName('field'))
    operation = ((p.Word(p.alphas).setResultsName('func_name') +
                  p.Suppress('(') + field_name.setResultsName('func_field') + p.Suppress(')'))
                 .setResultsName('operation'))
    field = field_name | operation
    is_kw = p.Keyword('is')
    negation = p.Optional(p.Keyword('not')).setParseAction(lambda t: bool(t)).setResultsName('negation')
    negation_does = (p.Optional(p.Keyword("doesn't") | p.Keyword("does not"))
                     .setParseAction(lambda t: bool(t)).setResultsName('negation'))
    equality = (field + p.Suppress('=') + value).setResultsName('=')
    inequality = (field + p.Suppress('!=') + value).setResultsName('!=')
    lt = (field + p.Suppress('<') + value).setResultsName('<')
    lte = (field + p.Suppress('<=') + value).setResultsName('<=')
    gt = (field + p.Suppress('>') + value).setResultsName('>')
    gte = (field + p.Suppress('>=') + value).setResultsName('>=')
    null_or_none = p.Keyword('null') | p.Keyword('none')
    null = (field + is_kw + negation + null_or_none).setResultsName('null')
    empty = (field + is_kw + negation + p.Keyword('empty')).setResultsName('empty')
    contains = (field + negation_does + (p.Keyword('contain') | p.Keyword('contains')) +
                string.setResultsName('value')).setResultsName('contains')
    startswith = (field + negation_does + (p.Keyword('start with') | p.Keyword('starts with')) +
                  string.setResultsName('value')).setResultsName('startswith')
    endswith = (field + negation_does + (p.Keyword('end with') | p.Keyword('ends with')) +
                string.setResultsName('value')).setResultsName('endswith')
    matches = (field + negation_does + (p.Keyword('match') | p.Keyword('matches')) +
               string.setResultsName('value')).setResultsName('matches')
    between = (field + negation +
               p.Keyword('between') + value.setResultsName('min') + p.Keyword('and') +
               value.setResultsName('max')).setResultsName('between')
    clause = ((equality | inequality | lte | gte | lt | gt | between |
               null | empty | contains | startswith | endswith | matches)
              .setParseAction(parse_clause).setResultsName('comparison'))
    oper_not = p.Keyword('not')
    oper_and = p.Keyword('and')
    oper_or = p.Keyword('or')
    filter = p.operatorPrecedence(clause, [
        (oper_not, 1, p.opAssoc.RIGHT),
        (oper_or, 2, p.opAssoc.LEFT),
        (p.Optional(oper_and, default='and'), 2, p.opAssoc.LEFT),
    ]).setParseAction(parse_filter)
    stmt = (p.stringStart() + model + p.Optional(filter).setResultsName('filter') +
            p.Optional(p.Keyword('using') + field_name.setResultsName('using')) +
            p.StringEnd()).setParseAction(parse)

    return stmt.parseString(query)[0]
