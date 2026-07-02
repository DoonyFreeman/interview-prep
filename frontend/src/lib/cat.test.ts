import { describe, expect, it } from "vitest";
import {
  ACHIEVEMENTS,
  DEFAULT_CAT_STATE,
  achievementsUnlocked,
  catStateToPatch,
  newlyUnlocked,
  daysBetween,
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
import type { CatThoughtApi, PetState } from "../api/types";

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
  it("unlocks the five new skins at their milestones", () => {
    expect(skinsUnlocked(5)).toContain("sakura");
    expect(skinsUnlocked(4)).not.toContain("sakura");
    expect(skinsUnlocked(10)).toContain("mint");
    expect(skinsUnlocked(21)).toContain("snow");
    expect(skinsUnlocked(45)).toContain("ember");
    expect(skinsUnlocked(60)).toContain("golden");
    expect(skinsUnlocked(59)).not.toContain("golden");
  });
});

describe("achievements", () => {
  it("unlocks by best streak, in threshold order", () => {
    expect(achievementsUnlocked(0)).toEqual([]);
    const week = achievementsUnlocked(7);
    expect(week.map((a) => a.id)).toEqual([
      "streak-1",
      "streak-3",
      "streak-5",
      "streak-7",
    ]);
    expect(achievementsUnlocked(100).length).toBe(ACHIEVEMENTS.length);
  });
  it("newlyUnlocked returns only the crossed thresholds", () => {
    expect(newlyUnlocked(0, 1).map((a) => a.id)).toEqual(["streak-1"]);
    expect(newlyUnlocked(5, 7).map((a) => a.id)).toEqual(["streak-7"]);
    expect(newlyUnlocked(7, 7)).toEqual([]);
    expect(newlyUnlocked(9, 14).map((a) => a.id)).toEqual([
      "streak-10",
      "streak-14",
    ]);
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

// --- pickThought -----------------------------------------------------------
function thought(
  course: string,
  lesson: string,
  anchor: string,
  term: string,
  definition = `About ${term}.`,
): CatThoughtApi {
  return {
    key: `${course}/${lesson}#${anchor}`,
    term,
    definition,
    course_slug: course,
    lesson_slug: lesson,
    anchor,
  };
}

const tGil = thought("python-core", "gil", "what-is-gil", "Что такое GIL");
const tDeco = thought(
  "python-idioms",
  "decorators",
  "decorators",
  "Декоратор",
);

describe("pickThought", () => {
  it("returns null with an empty pool", () => {
    expect(pickThought([], [], 1)).toBeNull();
  });

  it("maps a server thought to a concept-anchor link", () => {
    const got = pickThought([tGil], [], 1);
    expect(got).not.toBeNull();
    expect(got!.key).toBe("python-core/gil#what-is-gil");
    expect(got!.term).toBe("Что такое GIL");
    expect(got!.definition).toBe("About Что такое GIL.");
    expect(got!.link).toEqual({
      course_slug: "python-core",
      lesson_slug: "gil",
      anchor: "what-is-gil",
    });
  });

  it("skips a recently shown key while an alternative exists", () => {
    for (let seed = 1; seed < 8; seed++) {
      expect(pickThought([tGil, tDeco], [tGil.key], seed)!.key).toBe(tDeco.key);
      expect(pickThought([tGil, tDeco], [tDeco.key], seed)!.key).toBe(tGil.key);
    }
  });

  it("falls back to the full pool when every key is recent", () => {
    const got = pickThought([tGil, tDeco], [tGil.key, tDeco.key], 3);
    expect(got).not.toBeNull();
    expect([tGil.key, tDeco.key]).toContain(got!.key);
  });

  it("carries an empty definition through (code-only section)", () => {
    const bare = thought("c", "l", "a", "Заголовок", "");
    expect(pickThought([bare], [], 1)!.definition).toBe("");
  });

  it("is deterministic for a given seed", () => {
    expect(pickThought([tGil, tDeco], [], 42)!.key).toBe(
      pickThought([tGil, tDeco], [], 42)!.key,
    );
  });

  it("weights lessons equally regardless of concept count", () => {
    // lessonA has 4 concepts, lessonB has 1. Flat selection would pick lessonB
    // ~1/5 of the time; two-stage (lesson-first) should give it ~1/2.
    const big = ["a0", "a1", "a2", "a3"].map((a) =>
      thought("c", "big", a, a),
    );
    const small = [thought("c", "small", "s0", "s0")];
    const pool = [...big, ...small];
    let smallHits = 0;
    const N = 400;
    for (let seed = 1; seed <= N; seed++) {
      if (lessonOfKey(pickThought(pool, [], seed)!.key) === "c/small") {
        smallHits++;
      }
    }
    // Comfortably above the flat 1/5 (=80) baseline; centred near 1/2.
    expect(smallHits).toBeGreaterThan(150);
  });

  it("avoids repeating the lesson shown last when another exists", () => {
    const a = thought("c", "lessonA", "a0", "a0");
    const b = thought("c", "lessonB", "b0", "b0");
    // Last shown was a lessonA concept → next must come from lessonB.
    for (let seed = 1; seed < 12; seed++) {
      expect(lessonOfKey(pickThought([a, b], [a.key], seed)!.key)).toBe(
        "c/lessonB",
      );
    }
  });
});

function lessonOfKey(key: string): string {
  return key.split("#")[0];
}
