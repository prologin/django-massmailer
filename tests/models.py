import enum

from django.db import models


class SomeEnum(enum.Enum):
    foo = 42
    bar = "BAROO"


class SomeModel(models.Model):
    text_field = models.CharField(max_length=128)
    int_field = models.IntegerField()
    bool_field = models.BooleanField()


class SomeChild(models.Model):
    parent = models.ForeignKey(
        SomeModel, related_name='children', on_delete=models.CASCADE
    )
    child_field = models.CharField(max_length=128)
