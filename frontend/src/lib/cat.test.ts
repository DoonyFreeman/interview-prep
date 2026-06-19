import { describe, expect, it } from "vitest";
import {
  DEFAULT_CAT_STATE,
  daysBetween,
  pickThought,
  plainDefinition,
  resolveSkin,
  rolloverStreak,
  skinsUnlocked,
  stageForStreak,
  todayKey,
  type CatState,
} from "./cat";
import type {
  CourseProgressOut,
  GlossaryTerm,
  LessonProgressOut,
  ProgressOverviewOut,
} from "../api/types";

// --- date helpers ----------------------------------------------------------
describe("todayKey / daysBetween", () => {
  it("formats local date as YYYY-MM-DD", () => {
    expect(todayKey(new Date(2026, 5, 9))).toBe("2026-06-09");
  });
  it("counts whole calendar days", () => {
    expect(daysBetween("2026-06-09", "2026-06-10")).toBe(1);
    expect(daysBetween("2026-06-09", "2026-06-09")).toBe(0);
    expect(daysBetween("2026-06-09", "2026-06-12")).toBe(3);
    expect(daysBetween("2026-06-10", "2026-06-09")).toBe(-1);
    // across a month boundary
    expect(daysBetween("2026-05-31", "2026-06-01")).toBe(1);
  });
});

// --- streak rollover -------------------------------------------------------
describe("rolloverStreak", () => {
  const base: CatState = { ...DEFAULT_CAT_STATE };

  it("starts at 1 on first ever visit", () => {
    const next = rolloverStreak(base, "2026-06-09");
    expect(next.streak).toBe(1);
    expect(next.bestStreak).toBe(1);
    expect(next.lastActiveDay).toBe("2026-06-09");
  });

  it("is a no-op on the same day", () => {
    const s: CatState = { ...base, streak: 4, bestStreak: 4, lastActiveDay: "2026-06-09" };
    expect(rolloverStreak(s, "2026-06-09")).toBe(s);
  });

  it("increments on the next day", () => {
    const s: CatState = { ...base, streak: 4, bestStreak: 4, lastActiveDay: "2026-06-09" };
    const next = rolloverStreak(s, "2026-06-10");
    expect(next.streak).toBe(5);
    expect(next.bestStreak).toBe(5);
  });

  it("resets to 1 after a gap but keeps bestStreak", () => {
    const s: CatState = { ...base, streak: 9, bestStreak: 9, lastActiveDay: "2026-06-09" };
    const next = rolloverStreak(s, "2026-06-12");
    expect(next.streak).toBe(1);
    expect(next.bestStreak).toBe(9);
  });

  it("resets if the clock went backwards", () => {
    const s: CatState = { ...base, streak: 5, bestStreak: 5, lastActiveDay: "2026-06-09" };
    const next = rolloverStreak(s, "2026-06-08");
    expect(next.streak).toBe(1);
  });
});

// --- stages & skins --------------------------------------------------------
describe("stageForStreak", () => {
  it("grows with the streak", () => {
    expect(stageForStreak(0)).toBe("kitten");
    expect(stageForStreak(2)).toBe("kitten");
    expect(stageForStreak(3)).toBe("cat");
    expect(stageForStreak(6)).toBe("cat");
    expect(stageForStreak(7)).toBe("bigcat");
    expect(stageForStreak(13)).toBe("bigcat");
    expect(stageForStreak(14)).toBe("wizard");
    expect(stageForStreak(100)).toBe("wizard");
  });
});

describe("skinsUnlocked / resolveSkin", () => {
  it("unlocks skins at milestones", () => {
    expect(skinsUnlocked(0)).toEqual(["classic"]);
    expect(skinsUnlocked(3)).toEqual(["classic", "tabby"]);
    expect(skinsUnlocked(7)).toContain("tuxedo");
    expect(skinsUnlocked(30)).toContain("void");
  });
  it("clamps a locked skin choice to classic", () => {
    expect(resolveSkin("void", 5)).toBe("classic");
    expect(resolveSkin("tabby", 5)).toBe("tabby");
  });
});

// --- plainDefinition -------------------------------------------------------
describe("plainDefinition", () => {
  it("strips light markdown and collapses whitespace", () => {
    expect(plainDefinition("**GIL** is a `mutex`")).toBe("GIL is a mutex");
    expect(plainDefinition("see [docs](http://x)")).toBe("see docs");
  });
  it("truncates long text on a word boundary", () => {
    const out = plainDefinition("word ".repeat(60), 40);
    expect(out.length).toBeLessThanOrEqual(41);
    expect(out.endsWith("…")).toBe(true);
  });
});

// --- pickThought -----------------------------------------------------------
function term(
  slug: string,
  links: { course_slug: string; lesson_slug: string; anchor: string }[],
): GlossaryTerm {
  return {
    slug,
    term: `Term ${slug}`,
    category: "python",
    short_md: `Definition of ${slug}.`,
    aliases: [],
    links,
  };
}

function lesson(
  slug: string,
  attempted: number,
  mastered: number,
  completed = false,
): LessonProgressOut {
  return {
    slug,
    title: slug,
    completed,
    total_concepts: 5,
    attempted_concepts: attempted,
    mastered_concepts: mastered,
    due_concepts: 0,
    concepts: [],
  };
}

function progress(courses: CourseProgressOut[]): ProgressOverviewOut {
  return {
    total_concepts: 0,
    attempted_concepts: 0,
    mastered_concepts: 0,
    due_concepts: 0,
    courses,
  };
}

describe("pickThought", () => {
  const terms = [
    term("a", [{ course_slug: "python-core", lesson_slug: "gil", anchor: "gil" }]),
    term("b", [{ course_slug: "fastapi", lesson_slug: "di", anchor: "di" }]),
    term("c", [{ course_slug: "redis", lesson_slug: "ttl", anchor: "ttl" }]),
  ];

  it("returns null with no terms or no progress", () => {
    expect(pickThought([], progress([]), 1)).toBeNull();
    expect(pickThought(terms, undefined, 1)).toBeNull();
  });

  it("returns null when nothing has been attempted", () => {
    const p = progress([
      { slug: "python-core", title: "", total_concepts: 5, attempted_concepts: 0, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("gil", 0, 0)] },
    ]);
    expect(pickThought(terms, p, 1)).toBeNull();
  });

  it("counts a lesson marked done (no answers yet) as studied", () => {
    const p = progress([
      { slug: "python-core", title: "", total_concepts: 5, attempted_concepts: 0, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("gil", 0, 0, true)] },
    ]);
    const got = pickThought(terms, p, 1);
    expect(got).not.toBeNull();
    expect(got!.term).toBe("Term a");
    expect(got!.link.lesson_slug).toBe("gil");
  });

  it("only picks terms linked to a studied lesson", () => {
    const p = progress([
      { slug: "python-core", title: "", total_concepts: 5, attempted_concepts: 2, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("gil", 2, 0)] },
    ]);
    const got = pickThought(terms, p, 1);
    expect(got).not.toBeNull();
    expect(got!.term).toBe("Term a");
    expect(got!.link.lesson_slug).toBe("gil");
    expect(got!.definition).toBe("Definition of a.");
  });

  it("prefers a term linked to a mastered lesson", () => {
    const p = progress([
      { slug: "python-core", title: "", total_concepts: 5, attempted_concepts: 5, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("gil", 5, 0)] },
      { slug: "fastapi", title: "", total_concepts: 5, attempted_concepts: 5, mastered_concepts: 3, due_concepts: 0, lessons: [lesson("di", 5, 3)] },
    ]);
    // Both 'a' (attempted) and 'b' (mastered) qualify; mastered must win.
    for (let seed = 1; seed < 6; seed++) {
      expect(pickThought(terms, p, seed)!.term).toBe("Term b");
    }
  });

  it("is deterministic for a given seed", () => {
    const p = progress([
      { slug: "python-core", title: "", total_concepts: 5, attempted_concepts: 2, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("gil", 2, 0)] },
      { slug: "redis", title: "", total_concepts: 5, attempted_concepts: 2, mastered_concepts: 0, due_concepts: 0, lessons: [lesson("ttl", 2, 0)] },
    ]);
    expect(pickThought(terms, p, 42)!.term).toBe(pickThought(terms, p, 42)!.term);
  });
});
