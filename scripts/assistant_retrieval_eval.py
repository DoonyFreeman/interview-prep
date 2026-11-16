"""Compare BM25, E5, and RRF against labeled lesson sections offline."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from itertools import product
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from app.assistant.retrieval import (
    DEFAULT_CONTENT_DIR,
    DEFAULT_LIMIT,
    LessonHit,
    LessonRetriever,
    RetrievalUnavailable,
    distinct_sections,
    reciprocal_rank_fusion,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "backend" / "tests" / "fixtures" / "assistant_retrieval_eval.json"
CANDIDATES = (20, 40)
RRF_CONSTANTS = (10, 30, 60)


def _label(section: tuple[str, str, str]) -> str:
    course, lesson, anchor = section
    return f"{course}/{lesson}#{anchor}" if anchor else f"{course}/{lesson}"


def _metrics(
    top: tuple[LessonHit, ...], candidates: tuple[LessonHit, ...],
    expected: set[tuple[str, str, str]], limit: int,
) -> dict[str, float]:
    found = set()
    first_rank = None
    discounted_gain = 0.0
    for i, hit in enumerate(top, start=1):
        section = hit.section_key
        if section in expected:
            found.add(section)
            first_rank = first_rank or i
            discounted_gain += 1 / math.log2(i + 1)
    ideal_gain = sum(1 / math.log2(i + 1) for i in range(1, min(len(expected), limit) + 1))
    return {
        "hit_rate": float(bool(found)),
        "precision": len(found) / limit,
        "recall": len(found) / len(expected),
        "candidate_recall": len(expected.intersection(hit.section_key for hit in candidates)) / len(expected),
        "mrr": 1 / first_rank if first_rank else 0.0,
        "ndcg": discounted_gain / ideal_gain,
    }


def _rankings(lexical, dense, fixed_rrf):
    lexical_sizes = (fixed_rrf[0],) if fixed_rrf else CANDIDATES
    dense_sizes = (fixed_rrf[1],) if fixed_rrf else CANDIDATES
    constants = (fixed_rrf[2],) if fixed_rrf else RRF_CONSTANTS
    for count in lexical_sizes:
        yield f"bm25_{count}", lexical[:count]
    for count in dense_sizes:
        yield f"e5_{count}", dense[:count]
    for lexical_limit, dense_limit, constant in product(lexical_sizes, dense_sizes, constants):
        yield (
            f"rrf_{lexical_limit}_{dense_limit}_k{constant}",
            reciprocal_rank_fusion(lexical[:lexical_limit], dense[:dense_limit], constant=constant),
        )


def evaluate(
    retriever: LessonRetriever, cases: list[dict], *, limit: int,
    fixed_rrf: tuple[int, int, int] | None = None,
) -> dict:
    started = perf_counter()
    retriever.validate()
    validation_ms = (perf_counter() - started) * 1000
    by_split = defaultdict(list)
    times = []
    for case in cases:
        expected = {
            (entry["course_slug"], entry["lesson_slug"], entry["anchor"])
            for entry in case["relevant_sections"]
        }
        started = perf_counter()
        run = retriever.rank(
            case["query"],
            course_slug=case.get("course_slug"),
            lesson_slug=case.get("lesson_slug"),
            lexical_limit=fixed_rrf[0] if fixed_rrf else max(CANDIDATES),
            dense_limit=fixed_rrf[1] if fixed_rrf else max(CANDIDATES),
        )
        elapsed_ms = (perf_counter() - started) * 1000
        times.append(elapsed_ms)
        results = {}
        for name, hits in _rankings(run.lexical, run.dense, fixed_rrf):
            top = distinct_sections(hits, limit)
            result = {"top_sections": [_label(hit.section_key) for hit in top]}
            if expected:
                result.update(_metrics(top, hits, expected, limit))
            results[name] = result
        by_split[case["split"]].append({
            "id": case["id"],
            "expected_sections": sorted(_label(section) for section in expected),
            "query_ms": round(elapsed_ms, 2),
            "results": results,
        })

    warm_times = sorted(times[1:])
    timings = {"validate_ms": round(validation_ms, 2), "first_query_ms": round(times[0], 2)}
    if warm_times:
        timings.update({
            "warm_p50_ms": round(median(warm_times), 2),
            "warm_p95_ms": round(warm_times[math.ceil(.95 * len(warm_times)) - 1], 2),
        })

    summary = {}
    for split, rows in by_split.items():
        labeled = [row for row in rows if row["expected_sections"]]
        unlabeled = [row for row in rows if not row["expected_sections"]]
        methods = {}
        for name in rows[0]["results"]:
            scores = {}
            if labeled:
                for metric in ("hit_rate", "precision", "recall", "candidate_recall", "mrr", "ndcg"):
                    scores[metric] = round(mean(row["results"][name][metric] for row in labeled), 4)
            if unlabeled:
                scores["no_source_empty_rate"] = round(
                    mean(not row["results"][name]["top_sections"] for row in unlabeled), 4,
                )
            methods[name] = scores
        summary[split] = {
            "labeled_cases": len(labeled),
            "no_source_cases": len(unlabeled),
            "methods": methods,
        }

    return {"at": limit, "timing": timings, "summary": summary, "cases": dict(by_split)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--split", help="Evaluate only this labeled split")
    parser.add_argument(
        "--rrf", nargs=3, type=int, metavar=("BM25_CANDIDATES", "E5_CANDIDATES", "K"),
        help="Evaluate only this RRF configuration and its lexical and semantic baselines",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", type=Path, help="Write JSON to this path instead of stdout")
    args = parser.parse_args()
    if not 1 <= args.limit <= min(CANDIDATES):
        parser.error(f"--limit must be between 1 and {min(CANDIDATES)}")
    if args.rrf and (min(args.rrf[:2]) < args.limit or args.rrf[2] < 0):
        parser.error("--rrf requires candidate counts of at least --limit and a nonnegative K")

    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        if args.split:
            cases = [case for case in cases if case["split"] == args.split]
        if not cases:
            raise ValueError("There are no evaluation cases for the selected split")
        retriever = LessonRetriever(args.index, args.model_dir, content_dir=args.content_dir)
        report = evaluate(retriever, cases, limit=args.limit, fixed_rrf=tuple(args.rrf) if args.rrf else None)
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (RetrievalUnavailable, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"Retrieval evaluation failed: {exc}\n")


if __name__ == "__main__":
    main()
