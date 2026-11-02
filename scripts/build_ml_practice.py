#!/usr/bin/env python3
"""Build one offline HTML practice file from authored tasks and local fonts."""
from __future__ import annotations

import argparse
import base64
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'content/practice/ml-metrics.json'
TEMPLATE = ROOT / 'scripts/templates/ml-practice.html'
STATE_RUNTIME = ROOT / 'scripts/templates/ml-practice-state.js'
OUTPUT = ROOT / 'frontend/public/practice/ml-metrics.html'
GROUPS = {'basics', 'curves', 'averaging', 'regression'}


class AuthoredHTML(HTMLParser):
    """Only simple educational prose/tables; user notes are never HTML."""
    TAGS = {'p', 'ol', 'ul', 'li', 'strong', 'em', 'code', 'table', 'thead',
            'tbody', 'tr', 'th', 'td', 'div', 'br', 'sub', 'sup', 'span', 'small'}

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            raise ValueError(f'Unsupported authoring tag: {tag}')
        for name, value in attrs:
            if name not in {'class', 'scope', 'colspan', 'rowspan'}:
                raise ValueError(f'Unsupported authoring attribute: {name}')
            if value is None or '<' in value or '>' in value:
                raise ValueError('Invalid authoring attribute')

    def handle_endtag(self, tag):
        if tag not in self.TAGS:
            raise ValueError(f'Unsupported closing tag: {tag}')


def finite_numbers(values):
    return isinstance(values, list) and len(values) > 0 and all(
        isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
        for v in values
    )


def validate_plot(plot):
    if not isinstance(plot, dict):
        raise ValueError('Plot must be an object')
    kind = plot.get('type')
    if kind == 'blank':
        if plot.get('kind') not in {'roc', 'pr'}:
            raise ValueError('Blank plot needs roc/pr axes')
    elif kind == 'scores':
        scores, labels = plot.get('scores'), plot.get('labels')
        if not finite_numbers(scores) or not isinstance(labels, list) or len(labels) != len(scores):
            raise ValueError('Scores and labels must have matching lengths')
        if any(v < 0 or v > 1 for v in scores) or any(v not in (0, 1) for v in labels):
            raise ValueError('This practice score plot uses binary labels and scores in [0,1]')
    elif kind in {'roc', 'pr'}:
        points = plot.get('points')
        if not isinstance(points, list) or len(points) < 2 or any(
            not finite_numbers(p) or len(p) != 2 or any(v < 0 or v > 1 for v in p)
            for p in points
        ):
            raise ValueError('ROC/PR points must be coordinate pairs in [0,1]')
        if 'baseline' in plot and (not finite_numbers([plot['baseline']]) or not 0 <= plot['baseline'] <= 1):
            raise ValueError('Invalid plot baseline')
    elif kind == 'regression':
        actual, predicted = plot.get('actual'), plot.get('predicted')
        if not finite_numbers(actual) or not finite_numbers(predicted) or len(actual) != len(predicted):
            raise ValueError('Regression series must have matching lengths')
        if any(v < 0 for v in actual + predicted):
            raise ValueError('This practice regression plot expects non-negative values')
    else:
        raise ValueError(f'Unsupported plot: {kind}')


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('sources'), list) or not isinstance(data.get('tasks'), list):
        raise ValueError('Expected sources and tasks')
    source_ids = set()
    for source in data['sources']:
        for field in ('id', 'title', 'author', 'url', 'focus'):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise ValueError(f'Missing source {field}')
        url = urlsplit(source['url'])
        if url.scheme != 'https' or url.netloc != 'www.youtube.com' or url.path != '/watch':
            raise ValueError('Sources must link to original YouTube watch pages')
        if parse_qs(url.query).get('v') != [source['id']] or source['id'] in source_ids:
            raise ValueError('Source id/URL mismatch or duplicate')
        source_ids.add(source['id'])
    ids = set()
    for task in data['tasks']:
        if not isinstance(task.get('id'), str) or not re.fullmatch(r'\d{2}', task['id']) or task['id'] in ids:
            raise ValueError('Task id must be unique and two-digit')
        ids.add(task['id'])
        if task.get('group') not in GROUPS or task.get('source') not in source_ids:
            raise ValueError('Unknown task group/source')
        if not isinstance(task.get('minutes'), int) or not 1 <= task['minutes'] <= 60:
            raise ValueError('Invalid exercise duration')
        for field in ('title', 'statement', 'formula', 'solution'):
            if not isinstance(task.get(field), str) or not task[field].strip():
                raise ValueError(f'Missing task {field}')
            if field != 'title':
                parser = AuthoredHTML()
                parser.feed(task[field])
                parser.close()
        for field in ('plot', 'solutionPlot'):
            if field in task:
                validate_plot(task[field])
    if len(ids) != 14 or len(source_ids) != 5:
        raise ValueError('This practice requires 14 exercises and 5 video sources')


def embedded_fonts():
    folder = ROOT / 'frontend/node_modules/@fontsource-variable/geist'
    css = []
    for subset, unicode_range in [('latin', 'U+0000-024F,U+2000-206F,U+20A0-20CF'),
                                  ('cyrillic', 'U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116')]:
        font = folder / f'files/geist-{subset}-wght-normal.woff2'
        encoded = base64.b64encode(font.read_bytes()).decode('ascii')
        css.append("@font-face{font-family:Geist;font-style:normal;font-weight:100 900;"
                   "font-display:swap;src:url(data:font/woff2;base64," + encoded +
                   ") format('woff2');unicode-range:" + unicode_range + ';}')
    license_text = (folder / 'LICENSE').read_text(encoding='utf-8')
    if '-->' in license_text:
        raise ValueError('Font license cannot be embedded as an HTML comment')
    return '\n'.join(css), license_text


def build_html(data, template, fonts='', license_text='', state_runtime=None):
    validate(data)
    # Keep authored HTML inside inert JSON, even if a future paragraph contains
    # markup-looking text. The runtime only renders these validated fields;
    # local user notes use textarea.value and never pass through innerHTML.
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    encoded = encoded.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    if state_runtime is None:
        state_runtime = STATE_RUNTIME.read_text(encoding='utf-8')
    if '</script' in state_runtime.casefold():
        raise ValueError('Storage runtime cannot close its enclosing script')
    for marker in ('__PRACTICE_DATA__', '__EMBEDDED_FONTS__', '__FONT_LICENSE__', '__STATE_RUNTIME__'):
        if template.count(marker) != 1:
            raise ValueError(f'Template marker missing or duplicated: {marker}')
    return template.replace('__PRACTICE_DATA__', encoded).replace('__EMBEDDED_FONTS__', fonts).replace('__FONT_LICENSE__', license_text).replace('__STATE_RUNTIME__', state_runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    data = json.loads(DATA.read_text(encoding='utf-8'))
    fonts, license_text = embedded_fonts()
    result = build_html(data, TEMPLATE.read_text(encoding='utf-8'), fonts, license_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding='utf-8')
    print(f'Built {args.output.name}: {len(data["tasks"])} exercises, {len(result.encode())} bytes; offline HTML')


if __name__ == '__main__':
    main()
