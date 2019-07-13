from django.db.models import Case, When, Value, Sum, IntegerField


class CaseMapping(Case):
    """
    Wrapper around the Case annotation that provides a mapping between a field
    and an associated value.

    class Foo(models.Model):
        field = models.CharField(choices=['a', 'b', 'c'])

    Foo.objects
       .annotate(order=CaseMapping('field', [('a', 23), ('b', 11), ('c', 0)]))
       .order_by('-order')
    """

    def __init__(self, field, mapping, **kwargs):
        cases = [
            When(**{field: key, 'then': Value(value)})
            for key, value in mapping
        ]
        super().__init__(*cases, **kwargs)


class ConditionalSum(Sum):
    """
    Wrapper around the Sum annotation that provides a conditional sum.

    class Foo(models.Model):
        pass

    class Bar(models.Model):
        foo = models.ForeignKey(Bar, related_name='bars',
                                on_delete=models.CASCADE)
        ok = models.BooleanField()

    Foo.objects.annotate(
        ok_count=ConditionalSum(bars__state=True),
        nok_count=ConditionalSum(bars__state=False))
    """

    def __init__(self, **mapping):
        super(ConditionalSum, self).__init__(
            *[
                Case(
                    When(**{field: value, 'then': Value(1)}),
                    default=0,
                    output_field=IntegerField(),
                )
                for field, value in mapping.items()
            ]
        )
