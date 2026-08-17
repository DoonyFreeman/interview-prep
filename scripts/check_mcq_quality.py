#!/usr/bin/env python3
"""Check MCQ question files for the tells that let you pass a test without
knowing the material.

A multiple-choice question is only worth answering if the options are
indistinguishable to someone who hasn't learned the topic. Two habits break
that, and both are invisible when you read questions one at a time:

  1. **The length tell.** Authors write a careful, qualified correct answer and
     three throwaway distractors, so "pick the longest" wins. Shuffling the
     options (which the client does) hides the *position* of the answer but not
     its size.
  2. **The absurd distractor.** An option nobody would pick doesn't narrow
     anything down — a 4-option question with two jokes is a coin flip.

Run over any `tests.json` / `exam.json`:

    python3 scripts/check_mcq_quality.py content/courses/*/exam.json
    python3 scripts/check_mcq_quality.py --report content/courses/*/tests.json

Exit status is non-zero if any file fails, so it works as a pre-commit gate.
`--report` prints the statistics without failing, for surveying existing banks.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

#: The correct option may be at most this many times the mean distractor length
#: before "pick the longest" becomes a viable strategy.
MAX_LENGTH_RATIO = 1.35

#: A distractor shorter than this fraction of the correct answer reads as filler.
MIN_DISTRACTOR_RATIO = 0.5

#: Across a whole file, the correct answer should be the longest option no more
#: often than chance (1/4) plus slack — otherwise the bank leaks in aggregate
#: even if every individual question passes.
MAX_LONGEST_SHARE = 0.40


def iter_questions(path: Path):
    """Yield ``(lesson, concept, index, question)`` from a bank file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for lesson, concepts in data.items():
        for concept, questions in concepts.items():
            for i, q in enumerate(questions):
                yield lesson, concept, i, q


def check_question(q: dict) -> list[str]:
    """Structural + fairness problems with one question."""
    problems: list[str] = []
    options = q.get("options") or []
    correct = q.get("correct")

    if not q.get("text", "").strip():
        problems.append("empty text")
    if q.get("type", "single") == "single" and len(options) != 4:
        problems.append(f"{len(options)} options (want 4)")
    if len(options) != len(set(options)):
        problems.append("duplicate options")
    if not isinstance(correct, int) or not 0 <= correct < len(options):
        return problems + ["correct index out of range"]
    if not q.get("explanation_md", "").strip():
        problems.append("no explanation")

    right = len(options[correct])
    wrong = [len(o) for i, o in enumerate(options) if i != correct]
    if not wrong:
        return problems

    mean_wrong = statistics.mean(wrong)
    if mean_wrong and right / mean_wrong > MAX_LENGTH_RATIO:
        problems.append(
            f"length tell: correct is {right} chars vs {mean_wrong:.0f} avg "
            f"distractor ({right / mean_wrong:.2f}x, max {MAX_LENGTH_RATIO})"
        )
    for i, n in enumerate(wrong):
        if right and n / right < MIN_DISTRACTOR_RATIO:
            problems.append(
                f"distractor {i} is {n} chars against a {right}-char answer "
                "— too short to be plausible"
            )
            break
    return problems


def check_file(path: Path, report_only: bool) -> bool:
    total = 0
    longest = 0
    failures: list[str] = []
    ratios: list[float] = []

    for lesson, concept, i, q in iter_questions(path):
        total += 1
        problems = check_question(q)
        if problems:
            failures.append(f"  {lesson}/{concept}[{i}]: " + "; ".join(problems))

        options = q.get("options") or []
        correct = q.get("correct")
        if isinstance(correct, int) and 0 <= correct < len(options):
            lengths = [len(o) for o in options]
            if lengths[correct] == max(lengths) and lengths.count(max(lengths)) == 1:
                longest += 1
            wrong = [n for j, n in enumerate(lengths) if j != correct]
            if wrong and statistics.mean(wrong):
                ratios.append(lengths[correct] / statistics.mean(wrong))

    if total == 0:
        print(f"{path}: no questions")
        return True

    share = longest / total
    mean_ratio = statistics.mean(ratios) if ratios else 0
    summary = (
        f"{path}: {total} questions · correct-is-longest {share:.0%} "
        f"· mean length ratio {mean_ratio:.2f}"
    )

    ok = not failures and share <= MAX_LONGEST_SHARE
    if report_only:
        print(summary)
        return True

    print(("PASS  " if ok else "FAIL  ") + summary)
    if share > MAX_LONGEST_SHARE:
        print(
            f"  correct answer is the longest option in {share:.0%} of questions "
            f"(max {MAX_LONGEST_SHARE:.0%}) — guessable without reading"
        )
    for line in failures[:20]:
        print(line)
    if len(failures) > 20:
        print(f"  … and {len(failures) - 20} more")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--report",
        action="store_true",
        help="print statistics only, always exit 0 (for surveying a bank)",
    )
    args = parser.parse_args()

    ok = True
    for path in args.files:
        if not path.is_file():
            print(f"{path}: missing")
            ok = False
            continue
        ok &= check_file(path, args.report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
