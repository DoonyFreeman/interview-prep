"""Offline artifact checks, authoring boundary and independent numeric examples."""
from copy import deepcopy
from fractions import Fraction
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

from build_ml_practice import DATA, OUTPUT, ROOT, TEMPLATE, build_html, validate


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.outbound_assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'img', 'script', 'iframe', 'audio', 'video', 'source'} and attrs.get('src'):
            self.outbound_assets.append(attrs['src'])
        if tag == 'link' and attrs.get('href'):
            self.outbound_assets.append(attrs['href'])


class PracticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DATA.read_text(encoding='utf-8'))

    def test_complete_curriculum_and_source_links(self):
        validate(self.data)
        self.assertEqual([t['id'] for t in self.data['tasks']], [f'{i:02}' for i in range(1, 15)])
        self.assertEqual({t['group'] for t in self.data['tasks']}, {'basics', 'curves', 'averaging', 'regression'})
        for task in self.data['tasks']:
            self.assertIn('<ol>', task['solution'])

    def test_rejects_active_html_unknown_sources_and_invalid_plot_points(self):
        for field, value in [('statement', '<script>alert(1)</script>'),
                             ('formula', '<p onclick="alert(1)">test</p>')]:
            with self.subTest(field=field):
                invalid = deepcopy(self.data)
                invalid['tasks'][0][field] = value
                with self.assertRaises(ValueError):
                    validate(invalid)
        invalid = deepcopy(self.data)
        invalid['sources'][0]['url'] = 'https://example.invalid/watch?v=x'
        with self.assertRaises(ValueError):
            validate(invalid)
        invalid = deepcopy(self.data)
        invalid['tasks'][0]['plot'] = {'type': 'roc', 'points': [[0, 0], [1, float('nan')]]}
        with self.assertRaises(ValueError):
            validate(invalid)

    def test_embeds_inert_json_and_keeps_single_file_self_contained(self):
        data = deepcopy(self.data)
        data['tasks'][0]['title'] = '</script><script>alert(1)</script>'
        result = build_html(data, TEMPLATE.read_text(encoding='utf-8'))
        payload = re.search(r'<script id="practice-data" type="application/json">(.*?)</script>', result, re.S).group(1)
        self.assertNotIn('<', payload)
        self.assertEqual(json.loads(payload)['tasks'][0]['title'], data['tasks'][0]['title'])
        artifact = OUTPUT.read_text(encoding='utf-8')
        resources = Resources()
        resources.feed(artifact)
        self.assertEqual(resources.outbound_assets, [])
        self.assertIn('data:font/woff2;base64,', artifact)
        self.assertIn('SIL OPEN FONT LICENSE', artifact)
        self.assertNotIn('__PRACTICE_DATA__', artifact)
        self.assertNotIn('fetch(', artifact)
        self.assertNotIn('XMLHttpRequest', artifact)

    def test_regression_averaging_and_threshold_examples_independently(self):
        tasks = {t['id']: t for t in self.data['tasks']}
        scores = tasks['04']['plot']['scores']
        labels = tasks['04']['plot']['labels']
        rows = []
        for t in [1, .84, .54, 0]:
            tp = sum(y == 1 and s >= t for s, y in zip(scores, labels))
            fp = sum(y == 0 and s >= t for s, y in zip(scores, labels))
            rows.append((tp, fp, 6 - tp, 3 - fp))
        self.assertEqual(rows, [(1, 0, 5, 3), (4, 0, 2, 3), (4, 1, 2, 2), (6, 3, 0, 0)])
        roc = [[0, 0]]
        for threshold in sorted(set(scores), reverse=True):
            tp = sum(y == 1 and s >= threshold for s, y in zip(scores, labels))
            fp = sum(y == 0 and s >= threshold for s, y in zip(scores, labels))
            roc.append([fp/3, tp/6])
        self.assertEqual(tasks['05']['solutionPlot']['points'], roc)
        self.assertEqual(tasks['07']['solutionPlot']['baseline'], sum(labels)/len(labels))
        matrix = [[8, 1, 1], [1, 2, 1], [1, 0, 1]]
        f1, support = [], []
        for i in range(3):
            tp = matrix[i][i]
            fn = sum(matrix[i]) - tp
            fp = sum(row[i] for row in matrix) - tp
            f1.append(Fraction(2 * tp, 2 * tp + fp + fn))
            support.append(sum(matrix[i]))
        self.assertEqual(sum(f1) / 3, Fraction(62, 105))
        self.assertEqual(sum(n * f for n, f in zip(support, f1)) / 16, Fraction(97, 140))
        series = tasks['11']['plot']
        errors = [p-y for y, p in zip(series['actual'], series['predicted'])]
        self.assertEqual(sum(abs(e) for e in errors), 14)
        self.assertEqual(sum(e*e for e in errors), 108)
        self.assertEqual(1-Fraction(108, 200), Fraction(23, 50))


if __name__ == '__main__':
    unittest.main()
