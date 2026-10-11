"""官方目录 HTML 解析，保留表头、产品标题及 rowspan；Python 3.9+。"""
import json
import re
import gzip
from html.parser import HTMLParser
from pathlib import Path


def article(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b'\x1f\x8b'):
        raw = gzip.decompress(raw)
    text = raw.decode('utf-8')
    marker = 'window.__ICE_PAGE_PROPS__='
    if marker in text:
        data, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
        def find(value):
            if isinstance(value, dict):
                if isinstance(value.get('content'), str) and '<table' in value['content']:
                    return value['content']
                for child in value.values():
                    result = find(child)
                    if result: return result
            elif isinstance(value, list):
                for child in value:
                    result = find(child)
                    if result: return result
        content = find(data)
        if not content:
            raise ValueError('官方文章正文缺失: ' + str(path))
        text = content.replace('\\"', '"').replace('\\n', '\n')
    return text


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.heading = ''
        self.heading_parts = None
        self.table = self.row = self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.heading_parts = []
        if tag == 'table':
            self.table = {'heading': self.heading, 'rows': []}
        if tag == 'tr' and self.table is not None:
            self.row = []
        if tag in ('td', 'th') and self.row is not None:
            a = dict(attrs)
            self.cell = {'parts': [], 'rowspan': int(a.get('rowspan', 1)), 'colspan': int(a.get('colspan', 1))}

    def handle_data(self, data):
        if self.skip: return
        if self.heading_parts is not None: self.heading_parts.append(data)
        if self.cell is not None and data.strip(): self.cell['parts'].append(data.strip())

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip -= 1
        if tag in ('h1', 'h2', 'h3', 'h4') and self.heading_parts is not None:
            self.heading = re.sub(r'\s+', ' ', ' '.join(self.heading_parts)).strip()
            self.heading_parts = None
        if tag in ('td', 'th') and self.cell is not None:
            self.cell['text'] = re.sub(r'\s+', ' ', ' '.join(self.cell['parts'])).strip()
            self.row.append(self.cell)
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.table['rows'].append(self.row)
            self.row = None
        if tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def tables(path):
    parser = Tables()
    parser.feed(article(path))
    return parser.tables


def expanded(table):
    """填充 HTML rowspan/colspan，避免语言、模型和引擎错列。"""
    pending = {}
    for row in table['rows']:
        out, col = [], 0
        def carry():
            nonlocal col
            while col in pending:
                cell, remaining = pending[col]
                out.append(cell)
                if remaining == 1: del pending[col]
                else: pending[col] = (cell, remaining - 1)
                col += 1
        for cell in row:
            carry()
            for _ in range(cell['colspan']):
                out.append(cell)
                if cell['rowspan'] > 1: pending[col] = (cell, cell['rowspan'] - 1)
                col += 1
        carry()
        yield out
