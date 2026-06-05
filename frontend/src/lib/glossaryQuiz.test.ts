import { describe, expect, it } from "vitest";
import {
  bucketOf,
  buildQuiz,
  makeRng,
  truncateDefinition,
  type StatMap,
} from "./glossaryQuiz";
import type { GlossaryTerm, GlossaryTermStat } from "../api/types";

function term(slug: string, category: string): GlossaryTerm {
  return {
    slug,
    term: `Term ${slug}`,
    category,
    short_md: `Definition of ${slug}. It explains the concept clearly and in detail.`,
    aliases: [],
    links: [],
  };
}

// 8 python + 8 web terms
const TERMS: GlossaryTerm[] = [
  ...Array.from({ length: 8 }, (_, i) => term(`py${i}`, "python")),
  ...Array.from({ length: 8 }, (_, i) => term(`web${i}`, "web")),
];

function stat(over: Partial<GlossaryTermStat> & { term_slug: string }): GlossaryTermStat {
  return {
    seen: 0,
    correct: 0,
    last_correct: false,
    mastered: false,
    last_seen_at: new Date(0).toISOString(),
    ...over,
  };
}

const NO_STATS: StatMap = {};
const cfg = (over: Partial<Parameters<typeof buildQuiz>[2]> = {}) => ({
  categories: [] as string[],
  count: 10,
  types: ["def-to-term" as const],
  mode: "random" as const,
  ...over,
});

describe("buildQuiz", () => {
  it("produces the requested count with 4 options, one correct, unique slugs", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ count: 10 }), {
      rng: makeRng(1),
    });
    expect(q).toHaveLength(10);
    for (const question of q) {
      expect(question.options).toHaveLength(4);
      expect(question.options.filter((o) => o.correct)).toHaveLength(1);
      const slugs = question.options.map((o) => o.slug);
      expect(new Set(slugs).size).toBe(4);
      // the correct option corresponds to the subject term
      expect(question.options.find((o) => o.correct)!.slug).toBe(question.termSlug);
    }
  });

  it("never repeats a term within one quiz", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ count: 16 }), {
      rng: makeRng(7),
    });
    const subjects = q.map((x) => x.termSlug);
    expect(new Set(subjects).size).toBe(subjects.length);
  });

  it("clamps the count to the pool size", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ count: 999 }), {
      rng: makeRng(2),
    });
    expect(q).toHaveLength(TERMS.length);
  });

  it("filters subjects by selected category", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ categories: ["web"], count: 8 }), {
      rng: makeRng(3),
    });
    expect(q).toHaveLength(8);
    expect(q.every((x) => x.termSlug.startsWith("web"))).toBe(true);
  });

  it("is deterministic for a fixed seed", () => {
    const a = buildQuiz(TERMS, NO_STATS, cfg(), { rng: makeRng(42) });
    const b = buildQuiz(TERMS, NO_STATS, cfg(), { rng: makeRng(42) });
    expect(a.map((x) => x.id)).toEqual(b.map((x) => x.id));
    expect(a[0].options.map((o) => o.slug)).toEqual(b[0].options.map((o) => o.slug));
  });

  it("mode=mistakes selects only terms last answered wrong", () => {
    const stats: StatMap = {
      py0: stat({ term_slug: "py0", seen: 2, correct: 1, last_correct: false }),
      py1: stat({ term_slug: "py1", seen: 2, correct: 2, last_correct: true, mastered: true }),
    };
    const q = buildQuiz(TERMS, stats, cfg({ mode: "mistakes", count: 10 }), {
      rng: makeRng(5),
    });
    expect(q).toHaveLength(1);
    expect(q[0].termSlug).toBe("py0");
  });

  it("mode=weak selects new + weak, excludes mastered/learning", () => {
    const stats: StatMap = {
      // mastered → excluded
      py0: stat({ term_slug: "py0", seen: 3, correct: 3, last_correct: true, mastered: true }),
      // learning (correct<2, last correct, rate ok) → excluded
      py1: stat({ term_slug: "py1", seen: 1, correct: 1, last_correct: true }),
      // weak → included
      py2: stat({ term_slug: "py2", seen: 2, correct: 0, last_correct: false }),
      // all py3..py7 + web* have no stat → "new" → included
    };
    const q = buildQuiz(TERMS, stats, cfg({ mode: "weak", count: 100 }), {
      rng: makeRng(9),
    });
    const chosen = new Set(q.map((x) => x.termSlug));
    expect(chosen.has("py0")).toBe(false);
    expect(chosen.has("py1")).toBe(false);
    expect(chosen.has("py2")).toBe(true);
    // 16 total - 2 excluded = 14 eligible
    expect(q).toHaveLength(14);
  });

  it("returns empty when the pool is empty (unknown category)", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ categories: ["nope"] }));
    expect(q).toHaveLength(0);
  });

  it("supports term-to-def with truncated definition labels", () => {
    const q = buildQuiz(TERMS, NO_STATS, cfg({ types: ["term-to-def"], count: 3 }), {
      rng: makeRng(11),
    });
    for (const question of q) {
      expect(question.type).toBe("term-to-def");
      expect(question.promptIsMarkdown).toBe(false);
      // option labels are definitions (contain "Definition of"), not term names
      expect(question.options.every((o) => o.label.includes("Definition of"))).toBe(true);
    }
  });
});

describe("bucketOf", () => {
  it("classifies terms", () => {
    expect(bucketOf(undefined)).toBe("new");
    expect(bucketOf(stat({ term_slug: "x", seen: 0 }))).toBe("new");
    expect(
      bucketOf(stat({ term_slug: "x", seen: 3, correct: 3, last_correct: true, mastered: true })),
    ).toBe("mastered");
    expect(
      bucketOf(stat({ term_slug: "x", seen: 2, correct: 0, last_correct: false })),
    ).toBe("weak");
    expect(
      bucketOf(stat({ term_slug: "x", seen: 1, correct: 1, last_correct: true })),
    ).toBe("learning");
  });
});

describe("truncateDefinition", () => {
  it("strips markdown and clamps length", () => {
    const out = truncateDefinition("**Bold** `code` text. More sentences here.");
    expect(out).not.toContain("*");
    expect(out).not.toContain("`");
    expect(out.startsWith("Bold")).toBe(true);
  });
});
