from contextlib import contextmanager

import re
import uuid

from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor

PATTERN = re.compile(r'\{([\{%s])\s*(?P<data>.*?)\s*\1\}')


class Pre(Preprocessor):
    def __init__(self, ext):
        super().__init__()
        self.ext = ext

    def replace(self, m):
        key = '§§§{}§§§'.format(uuid.uuid4())
        self.ext.placeholders[key] = '{{{tag} {data} {tag}}}'.format(
            tag=m.group(1), data=m.group('data')
        )
        return key

    def run(self, lines):
        return [PATTERN.sub(self.replace, line) for line in lines]


class Post(Postprocessor):
    def __init__(self, ext):
        super().__init__()
        self.ext = ext

    def replace(self, m):
        return self.ext.placeholders[m.group(1)]

    def run(self, text):
        if not self.ext.placeholders:
            return text
        pat = '({})'.format(
            '|'.join(re.escape(_) for _ in self.ext.placeholders)
        )
        return re.sub(pat, self.replace, text)


class JinjaEscapeExtension(Extension):
    def __init__(self):
        super(JinjaEscapeExtension, self).__init__()
        self.placeholders = {}

    def extendMarkdown(self, md):
        md.preprocessors.add('jinja-pre', Pre(self), '_begin')
        md.postprocessors.add('jinja-post', Post(self), '_end')


def get_attr_rec(item, field):
    '''
    Same as getattr(item, field) but behaves recursivelly with the
    field__subfield syntax.
    '''
    for key in field.split('__'):
        item = getattr(item, key)

    return item


def get_field_rec(model, field):
    '''
    Select a field from an django model, behaves recursivelly with the
    field__subfield syntax.
    '''
    for key in field.split('__'):
        model = model._meta.get_field(key).related_model

    return model
