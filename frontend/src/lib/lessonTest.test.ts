import { describe, it, expect } from "vitest";
import {
  makeRng,
  shuffle,
  prepareTest,
  mistakeSlugs,
  scorePct,
  toResultItems,
  theoryPath,
  type Answer,
} from "./lessonTest";
import type { McqQuestion } from "../api/types";

function mcq(slug: string, correctIndex = 0): McqQuestion {
  return {
    slug,
    type: "single",
    text: `q ${slug}`,
    options: ["a", "b", "c", "d"],
    correct_index: correctIndex,
    explanation_md: "because",
    concept_slug: `c-${slug}`,
    concept_title: `Concept ${slug}`,
    anchor: `anchor-${slug}`,
    difficulty: 2,
  };
}

const BANK: McqQuestion[] = [mcq("q0", 0), mcq("q1", 1), mcq("q2", 2), mcq("q3", 3)];

describe("prepareTest", () => {
  it("returns one prepared item per question with exactly one correct option", () => {
    const prepared = prepareTest(BANK, { seed: 1 });
    expect(prepared).toHaveLength(BANK.length);
    for (const p of prepared) {
      expect(p.options).toHaveLength(4);
      expect(p.options.filter((o) => o.correct)).toHaveLength(1);
      // labels preserved as a set
      expect(new Set(p.options.map((o) => o.label))).toEqual(
        new Set(["a", "b", "c", "d"]),
      );
    }
  });

  it("marks the option whose original index was correct_index", () => {
    const prepared = prepareTest([mcq("only", 2)], { seed: 5 });
    const correct = prepared[0].options.find((o) => o.correct);
    expect(correct?.label).toBe("c"); // index 2 -> "c"
  });

  it("is deterministic for a given seed", () => {
    const a = prepareTest(BANK, { seed: 42 });
    const b = prepareTest(BANK, { seed: 42 });
    expect(a.map((p) => p.slug)).toEqual(b.map((p) => p.slug));
    expect(a[0].options.map((o) => o.label)).toEqual(
      b[0].options.map((o) => o.label),
    );
  });

  it("filters to onlySlugs (review mistakes)", () => {
    const prepared = prepareTest(BANK, { onlySlugs: ["q1", "q3"], seed: 1 });
    expect(prepared.map((p) => p.slug).sort()).toEqual(["q1", "q3"]);
  });

  it("caps the count with limit", () => {
    const prepared = prepareTest(BANK, { limit: 2, seed: 1 });
    expect(prepared).toHaveLength(2);
  });

  it("handles an empty bank", () => {
    expect(prepareTest([], { seed: 1 })).toEqual([]);
  });
});

describe("mistakeSlugs", () => {
  it("returns slugs answered wrong last time, in bank order", () => {
    const stats = [
      { mcq_slug: "q0", last_correct: true, seen: 1 },
      { mcq_slug: "q1", last_correct: false, seen: 1 },
      { mcq_slug: "q2", last_correct: false, seen: 0 }, // never seen -> excluded
      { mcq_slug: "q3", last_correct: false, seen: 2 },
    ];
    expect(mistakeSlugs(BANK, stats)).toEqual(["q1", "q3"]);
  });
});

describe("scoring", () => {
  const answers: Answer[] = [
    { slug: "q0", conceptTitle: "", anchor: "", text: "", correct: true },
    { slug: "q1", conceptTitle: "", anchor: "", text: "", correct: false },
    { slug: "q2", conceptTitle: "", anchor: "", text: "", correct: true },
    { slug: "q3", conceptTitle: "", anchor: "", text: "", correct: true },
  ];

  it("scorePct rounds correct/total", () => {
    expect(scorePct(answers)).toBe(75);
    expect(scorePct([])).toBe(0);
  });

  it("toResultItems maps slug + correct", () => {
    expect(toResultItems(answers)).toEqual([
      { slug: "q0", correct: true },
      { slug: "q1", correct: false },
      { slug: "q2", correct: true },
      { slug: "q3", correct: true },
    ]);
  });
});

describe("shuffle + rng", () => {
  it("preserves the multiset of elements", () => {
    const out = shuffle([1, 2, 3, 4, 5], makeRng(7));
    expect(out.slice().sort()).toEqual([1, 2, 3, 4, 5]);
  });

  it("same seed -> same order", () => {
    expect(shuffle([1, 2, 3, 4, 5], makeRng(7))).toEqual(
      shuffle([1, 2, 3, 4, 5], makeRng(7)),
    );
  });
});

// --- origin (mixed test spans lessons) --------------------------------------
describe("origin", () => {
  const q = (over: Partial<McqQuestion> = {}): McqQuestion => ({
    slug: "s",
    type: "single",
    text: "t",
    options: ["a", "b"],
    correct_index: 0,
    explanation_md: "",
    concept_slug: "c",
    concept_title: "C",
    anchor: "anchor",
    difficulty: 3,
    ...over,
  });

  it("falls back to the run's origin when a question carries none", () => {
    const [p] = prepareTest([q()], {
      origin: { courseSlug: "python-core", lessonSlug: "gil" },
    });
    expect(theoryPath(p)).toBe("/courses/python-core/lessons/gil#anchor");
  });

  it("prefers the question's own origin over the fallback", () => {
    const [p] = prepareTest([q({ course_slug: "redis", lesson_slug: "keys" })], {
      origin: { courseSlug: "python-core", lessonSlug: "gil" },
    });
    expect(theoryPath(p)).toBe("/courses/redis/lessons/keys#anchor");
  });

  it("yields no path at all when the origin is unknown", () => {
    expect(theoryPath({ anchor: "x" })).toBe("");
  });
});
