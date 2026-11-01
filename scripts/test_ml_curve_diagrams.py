"""Offline checks for the authored example, especially tied zero scores."""
from fractions import Fraction
import unittest
import xml.etree.ElementTree as ET

from reportlab.graphics import renderSVG

from build_ml_curve_diagrams import counts_at, curve_rows, example_areas, roc_diagram


class ExampleTests(unittest.TestCase):
    def test_selected_thresholds(self):
        for threshold, expected in [
            (1.01, (0, 0, 6, 3)), (1, (1, 0, 5, 3)),
            (.84, (4, 0, 2, 3)), (.54, (4, 1, 2, 2)),
            (0, (6, 3, 0, 0)),
        ]:
            with self.subTest(threshold=threshold):
                self.assertEqual(counts_at(threshold), expected)

    def test_equal_scores_are_included_together(self):
        rows = curve_rows()
        self.assertEqual(len(rows), 7)  # no predictions + six unique scores
        self.assertEqual(rows[-2][1:], (4, 1, 2, 2))
        self.assertEqual(rows[-1][1:], (6, 3, 0, 0))
        self.assertEqual(counts_at(.000001), (4, 1, 2, 2))

    def test_areas_use_ties_and_distinguish_ap_from_trapezoids(self):
        self.assertEqual(example_areas(), {
            'roc_auc': Fraction(7, 9),
            'ap': Fraction(8, 9),
            'pr_auc': Fraction(41, 45),
        })

    def test_svg_dashes_do_not_retrace_closed_lines(self):
        root = ET.fromstring(renderSVG.drawToString(roc_diagram()))
        dashed = [e for e in root.iter() if 'stroke-dasharray:' in e.get('style', '')]
        self.assertEqual(len(dashed), 2)  # score threshold and ROC baseline
        for element in dashed:
            self.assertFalse(element.get('d', '').strip().upper().endswith('Z'))


if __name__ == '__main__':
    unittest.main()
