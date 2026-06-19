import { describe, expect, it } from "vitest";
import {
  DEFAULT_CAT_STATE,
  catStateToPatch,
  daysBetween,
  matchConceptToTerm,
  petDiff,
  petToCatState,
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
  ConceptProgressOut,
  CourseProgressOut,
  GlossaryTerm,
  LessonProgressOut,
  PetState,
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

// --- server <-> client mapping ---------------------------------------------
describe("petToCatState / catStateToPatch / petDiff", () => {
  const server: PetState = {
    name: "Мурзик",
    skin: "tabby",
    streak: 4,
    best_streak: 5,
    last_active_day: "2026-06-18",
    hidden: false,
  };

  it("maps snake_case server state to camelCase", () => {
    expect(petToCatState(server)).toEqual({
      name: "Мурзик",
      skin: "tabby",
      streak: 4,
      bestStreak: 5,
      lastActiveDay: "2026-06-18",
      hidden: false,
    });
  });

  it("clamps a locked skin when mapping in", () => {
    expect(petToCatState({ ...server, skin: "void", best_streak: 2 }).skin).toBe(
      "classic",
    );
  });

  it("round-trips through a PATCH body", () => {
    expect(catStateToPatch(petToCatState(server))).toEqual({
      name: "Мурзик",
      skin: "tabby",
      streak: 4,
      best_streak: 5,
      last_active_day: "2026-06-18",
      hidden: false,
    });
  });

  it("petDiff returns null when nothing changed", () => {
    const s = petToCatState(server);
    expect(petDiff(s, s)).toBeNull();
  });

  it("petDiff emits only the changed fields (snake_case)", () => {
    const s = petToCatState(server); // streak 4, bestStreak 5
    const next = { ...s, streak: 5, lastActiveDay: "2026-06-19" };
    expect(petDiff(s, next)).toEqual({
      streak: 5,
      last_active_day: "2026-06-19",
    });
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

// --- matchConceptToTerm ----------------------------------------------------
function gterm(slug: string, name: string, aliases: string[] = []): GlossaryTerm {
  return {
    slug,
    term: name,
    category: "python",
    short_md: `Definition of ${slug}.`,
    aliases,
    links: [],
  };
}

const TERMS = [
  gterm("gil", "GIL (Global Interpreter Lock)"),
  gterm("decorator", "Декоратор"),
  gterm("asyncio", "asyncio", ["асинхронность"]),
];

describe("matchConceptToTerm", () => {
  it("matches a term name appearing as tokens in the concept title", () => {
    expect(matchConceptToTerm("Что такое GIL и зачем он нужен", TERMS)?.slug).toBe("gil");
    expect(matchConceptToTerm("Декоратор и его применение", TERMS)?.slug).toBe(
      "decorator",
    );
  });
  it("matches via the parenthetical english", () => {
    expect(matchConceptToTerm("Зачем нужен global interpreter lock", TERMS)?.slug).toBe(
      "gil",
    );
  });
  it("matches via an alias", () => {
    expect(matchConceptToTerm("Асинхронность в Python", TERMS)?.slug).toBe("asyncio");
  });
  it("returns null when nothing matches", () => {
    expect(matchConceptToTerm("Совершенно другая тема", TERMS)).toBeNull();
  });
});

// --- pickThought -----------------------------------------------------------
function concept(title: string, anchor: string): ConceptProgressOut {
  return {
    slug: anchor,
    title,
    anchor,
    attempted: false,
    mastered: false,
    reps: 0,
    last_score: 0,
    due_at: null,
    due: false,
  };
}

function lesson(
  slug: string,
  completed: boolean,
  concepts: ConceptProgressOut[],
): LessonProgressOut {
  return {
    slug,
    title: slug,
    completed,
    total_concepts: concepts.length,
    attempted_concepts: 0,
    mastered_concepts: 0,
    due_concepts: 0,
    concepts,
  };
}

function course(slug: string, lessons: LessonProgressOut[]): CourseProgressOut {
  return {
    slug,
    title: slug,
    total_concepts: 0,
    attempted_concepts: 0,
    mastered_concepts: 0,
    due_concepts: 0,
    lessons,
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

const cGil = concept("Что такое GIL", "what-is-gil");
const cDeco = concept("Декоратор и его применение", "decorators");

describe("pickThought", () => {
  it("returns null with no progress", () => {
    expect(pickThought(TERMS, undefined, [], 1)).toBeNull();
  });

  it("returns null when no lesson is completed (attempts don't count)", () => {
    const p = progress([course("python-core", [lesson("gil", false, [cGil])])]);
    expect(pickThought(TERMS, p, [], 1)).toBeNull();
  });

  it("returns a matched term + concept-anchor link for a completed lesson", () => {
    const p = progress([course("python-core", [lesson("gil", true, [cGil])])]);
    const got = pickThought(TERMS, p, [], 1);
    expect(got).not.toBeNull();
    expect(got!.key).toBe("gil");
    expect(got!.term).toBe("GIL (Global Interpreter Lock)");
    expect(got!.definition).toBe("Definition of gil.");
    expect(got!.link).toEqual({
      course_slug: "python-core",
      lesson_slug: "gil",
      anchor: "what-is-gil",
    });
  });

  it("only draws from completed lessons", () => {
    const p = progress([
      course("python-core", [lesson("gil", true, [cGil])]),
      course("python-idioms", [lesson("decorators", false, [cDeco])]),
    ]);
    for (let seed = 1; seed < 8; seed++) {
      expect(pickThought(TERMS, p, [], seed)!.key).toBe("gil");
    }
  });

  it("skips a recently shown key while an alternative exists", () => {
    const p = progress([
      course("python-core", [lesson("gil", true, [cGil])]),
      course("python-idioms", [lesson("decorators", true, [cDeco])]),
    ]);
    for (let seed = 1; seed < 8; seed++) {
      expect(pickThought(TERMS, p, ["gil"], seed)!.key).toBe("decorator");
      expect(pickThought(TERMS, p, ["decorator"], seed)!.key).toBe("gil");
    }
  });

  it("falls back to the bare concept when no term matches", () => {
    const cMisc = concept("Совсем другое", "misc");
    const p = progress([course("python-core", [lesson("x", true, [cMisc])])]);
    const got = pickThought(TERMS, p, [], 1);
    expect(got!.term).toBe("Совсем другое");
    expect(got!.definition).toBe("");
    expect(got!.link.anchor).toBe("misc");
    // Same when the glossary hasn't loaded.
    expect(pickThought([], p, [], 1)!.term).toBe("Совсем другое");
  });

  it("is deterministic for a given seed", () => {
    const p = progress([
      course("python-core", [lesson("gil", true, [cGil])]),
      course("python-idioms", [lesson("decorators", true, [cDeco])]),
    ]);
    expect(pickThought(TERMS, p, [], 42)!.key).toBe(pickThought(TERMS, p, [], 42)!.key);
  });
});
