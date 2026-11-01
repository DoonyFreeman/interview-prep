#!/usr/bin/env python3
"""Offline vector figures for the ML sheet; ReportLab only, no app dependency."""
from fractions import Fraction
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Circle, Drawing, PolyLine, Rect, String
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[1]
# Rounded values transcribed from the user's screenshot of the linked video.
EXAMPLE = ((0, 0), (0, 0), (0, 1), (0, 1), (.545455, 0),
           (.849057, 1), (.966292, 1), (.968750, 1), (1, 1))
INK = '#263247'
MUTED = '#64748b'
PURPLE = '#6650bf'
ORANGE = '#c16c23'
GRID = '#d9dfe8'


def counts_at(threshold):
    """TP, FP, FN, TN for the fixed example; equality predicts class 1."""
    tp = sum(label == 1 and score >= threshold for score, label in EXAMPLE)
    fp = sum(label == 0 and score >= threshold for score, label in EXAMPLE)
    return tp, fp, 6 - tp, 3 - fp


def curve_rows():
    thresholds = [float('inf'), *sorted({s for s, _ in EXAMPLE}, reverse=True)]
    return [(t, *counts_at(t)) for t in thresholds]


def example_areas():
    roc = []
    pr = []
    ap = Fraction(0)
    previous_recall = Fraction(0)
    for _, tp, fp, fn, tn in curve_rows():
        recall = Fraction(tp, tp + fn)
        precision = Fraction(tp, tp + fp) if tp + fp else Fraction(1)
        roc.append((Fraction(fp, fp + tn), recall))
        pr.append((recall, precision))
        ap += (recall - previous_recall) * precision
        previous_recall = recall

    def trapezoids(points):
        return sum(((x2 - x1) * (y1 + y2) / 2
                    for (x1, y1), (x2, y2) in zip(points, points[1:])), Fraction(0))

    return {'roc_auc': trapezoids(roc), 'ap': ap, 'pr_auc': trapezoids(pr)}


def label(d, x, y, text, size=14, color=INK, anchor='start'):
    d.add(String(x, y, text, fontName='Helvetica', fontSize=size,
                 fillColor=colors.HexColor(color), textAnchor=anchor))


def segment(d, x1, y1, x2, y2, color=GRID, width=1, dash=None):
    # renderSVG closes Line paths with Z, retracing the segment and filling
    # dashed gaps on the return stroke. An open PolyLine preserves the dashes.
    d.add(PolyLine([x1, y1, x2, y2], strokeColor=colors.HexColor(color),
                   strokeWidth=width, strokeDashArray=dash, fillColor=None))


def axes(d, x, y, width, height, xlabel, ylabel):
    for tick in (0, .5, 1):
        segment(d, x + tick * width, y, x + tick * width, y + height)
        segment(d, x, y + tick * height, x + width, y + tick * height)
        label(d, x + tick * width, y - 18, f'{tick:g}', color=MUTED, anchor='middle')
        label(d, x - 12, y + tick * height - 4, f'{tick:g}', color=MUTED, anchor='end')
    segment(d, x, y, x + width, y, MUTED)
    segment(d, x, y, x, y + height, MUTED)
    label(d, x + width, y - 38, xlabel, anchor='end')
    label(d, x, y + height + 15, ylabel)


def curve(d, points, x, y, width, height):
    coords = [(x + float(px) * width, y + float(py) * height) for px, py in points]
    d.add(PolyLine([v for xy in coords for v in xy],
                   strokeColor=colors.HexColor(PURPLE), strokeWidth=3))
    for px, py in coords:
        d.add(Circle(px, py, 3.5, fillColor=colors.HexColor(PURPLE), strokeColor=None))


def roc_diagram():
    d = Drawing(500, 380)
    d.add(Rect(0, 0, 500, 380, fillColor=colors.white, strokeColor=None))
    label(d, 52, 358, 'Scores: t = 0.54', size=17)
    label(d, 310, 358, 'class 1', color=PURPLE)
    label(d, 401, 358, 'class 0', color=ORANGE)
    # Same score distribution as the screenshot; color is the true class.
    x, y, w, h = 52, 250, 410, 75
    for tick in (0, .5, 1):
        segment(d, x, y + tick * h, x + w, y + tick * h)
        label(d, x - 12, y + tick * h - 4, f'{tick:g}', color=MUTED, anchor='end')
    for index, (score, actual) in enumerate(EXAMPLE):
        px = x + index * w / 8
        color = PURPLE if actual else ORANGE
        d.add(Circle(px, y + score * h, 5, fillColor=colors.HexColor(color), strokeColor=None))
        label(d, px, y - 19, str(index), size=13, color=MUTED, anchor='middle')
    segment(d, x, y + .54 * h, x + w, y + .54 * h, ORANGE, 2, [5, 3])
    label(d, x + w, y + .54 * h + 7, 't = 0.54', color=ORANGE, anchor='end')

    x, y, w, h = 52, 54, 410, 148
    axes(d, x, y, w, h, 'FPR', 'TPR = Recall')
    segment(d, x, y, x + w, y + h, MUTED, 1, [4, 4])
    points = [(Fraction(fp, 3), Fraction(tp, 6)) for _, tp, fp, _, _ in curve_rows()]
    curve(d, points, x, y, w, h)
    label(d, x + 10, y + 7, 't > 1', size=13)
    label(d, x + 10, y + h / 6 + 4, 't = 1', size=13)
    label(d, x + 10, y + h * 2 / 3 + 7, 't = 0.84', size=13)
    label(d, x + w / 3 + 10, y + h * 2 / 3 - 19, 't = 0.54', size=13, color=ORANGE)
    label(d, x + w - 5, y + h + 9, 't = 0', size=13, anchor='end')
    d.add(Circle(x + w / 3, y + h * 2 / 3, 5,
                 fillColor=colors.HexColor(ORANGE), strokeColor=None))
    return d


def pr_diagram():
    d = Drawing(500, 300)
    d.add(Rect(0, 0, 500, 300, fillColor=colors.white, strokeColor=None))
    x, y, w, h = 52, 64, 410, 182
    axes(d, x, y, w, h, 'Recall', 'Precision')
    segment(d, x, y + h * 2 / 3, x + w, y + h * 2 / 3, MUTED, 1, [4, 4])
    label(d, x + 12, y + h * 2 / 3 - 20, 'baseline = 6/9', size=13, color=MUTED)
    points = [(Fraction(tp, 6), Fraction(tp, tp + fp) if tp + fp else Fraction(1))
              for _, tp, fp, _, _ in curve_rows()]
    curve(d, points, x, y, w, h)
    label(d, x + 5, y + h - 20, '(0, 1)*', size=13)
    label(d, x + w / 6, y + h + 10, 't = 1', size=13, anchor='middle')
    label(d, x + w * 2 / 3, y + h + 10, 't = 0.84', size=13, anchor='middle')
    label(d, x + w * 2 / 3 - 10, y + h * .8 - 20, 't = 0.54', size=13, color=ORANGE, anchor='end')
    label(d, x + w - 5, y + h * 2 / 3 - 20, 't = 0', size=13, anchor='end')
    d.add(Circle(x + w * 2 / 3, y + h * .8, 5,
                 fillColor=colors.HexColor(ORANGE), strokeColor=None))
    label(d, 52, 8, '* (Recall=0; Precision=1)', size=13, color=MUTED)
    return d


DIAGRAMS = {
    '/cheatsheet-media/ml-roc-thresholds.svg': roc_diagram,
    '/cheatsheet-media/ml-pr-thresholds.svg': pr_diagram,
}


def pdf_diagram(path, width):
    if path not in DIAGRAMS:
        raise ValueError(f'Unknown ML diagram: {path}')
    drawing = DIAGRAMS[path]()
    factor = width / drawing.width
    drawing.scale(factor, factor)
    drawing.width *= factor
    drawing.height *= factor
    return drawing


def main():
    output = ROOT / 'frontend/public/cheatsheet-media'
    output.mkdir(parents=True, exist_ok=True)
    for path, build in DIAGRAMS.items():
        renderSVG.drawToFile(build(), str(output / Path(path).name))


if __name__ == '__main__':
    main()
