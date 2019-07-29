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
