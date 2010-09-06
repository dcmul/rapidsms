
from text import Text
from section import Section
from paragraph import Paragraph
from hline import HLine

class Document(object):
    def __init__(self, title, subtitle=''):
        self.title = title
        self.subtitle = subtitle
        self.contents = []

    def add_section(self, name):
        self.contents.append(Section(name))

    def add_paragraph(self, ptext):
        self.contents.append(Paragraph(ptext))

    def add_hline(self):
        self.contents.append(HLine())

