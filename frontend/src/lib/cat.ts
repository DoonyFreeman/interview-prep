// Pure, deterministic logic for the corner "tamagotchi" cat. No React, no
// network, no localStorage here — just functions over plain data so they're
// trivially testable (see cat.test.ts). The hook (cat/useCat.ts) owns side
// effects (persistence, timers); the widget owns rendering.
import type { CatThoughtApi, PetState } from "../api/types";
import { makeRng } from "./glossaryQuiz";

// --- Persistent state ------------------------------------------------------

export type CatStage = "kitten" | "cat" | "bigcat" | "wizard";
export type CatSkin =
  | "classic"
  | "tabby"
  | "tuxedo"
  | "calico"
  | "void"
  | "sakura"
  | "mint"
  | "snow"
  | "ember"
  | "golden";

/** Client-side (camelCase) mirror of the server `PetState`. */
export interface CatState {
  /** The pet's name (empty → a default label is shown). */
  name: string;
  /** Current daily streak (consecutive days the app was opened). */
  streak: number;
  /** All-time best streak — gates which skins are unlocked. */
  bestStreak: number;
  /** Last day the app was opened, local "YYYY-MM-DD", or null on first run. */
  lastActiveDay: string | null;
  /** Chosen skin (must stay within `skinsUnlocked`). */
  skin: CatSkin;
  /** Whether the user collapsed the cat to a tiny icon. */
  hidden: boolean;
}

export const DEFAULT_CAT_STATE: CatState = {
  name: "",
  streak: 0,
  bestStreak: 0,
  lastActiveDay: null,
  skin: "classic",
  hidden: false,
};

/** Server `PetState` (snake_case) → client `CatState` (camelCase). */
export function petToCatState(p: PetState): CatState {
  return {
    name: p.name,
    streak: p.streak,
    bestStreak: p.best_streak,
    lastActiveDay: p.last_active_day,
    skin: resolveSkin(p.skin as CatSkin, p.best_streak),
    hidden: p.hidden,
  };
}

/** Client `CatState` → a server PATCH body (snake_case). */
export function catStateToPatch(s: CatState): Partial<PetState> {
  return {
    name: s.name,
    streak: s.streak,
    best_streak: s.bestStreak,
    last_active_day: s.lastActiveDay,
    skin: s.skin,
    hidden: s.hidden,
  };
}

/** Field-level diff (server vs. desired) → minimal PATCH, or null if equal. */
export function petDiff(server: CatState, desired: CatState): Partial<PetState> | null {
  const patch: Partial<PetState> = {};
  if (server.name !== desired.name) patch.name = desired.name;
  if (server.skin !== desired.skin) patch.skin = desired.skin;
  if (server.streak !== desired.streak) patch.streak = desired.streak;
  if (server.bestStreak !== desired.bestStreak) patch.best_streak = desired.bestStreak;
  if (server.lastActiveDay !== desired.lastActiveDay)
    patch.last_active_day = desired.lastActiveDay;
  if (server.hidden !== desired.hidden) patch.hidden = desired.hidden;
  return Object.keys(patch).length ? patch : null;
}

/** Local calendar day as "YYYY-MM-DD" (not UTC — the streak is about *their* day). */
export function todayKey(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Whole calendar days from `a` to `b` (both "YYYY-MM-DD"). Positive if b > a. */
export function daysBetween(a: string, b: string): number {
  const pa = a.split("-").map(Number);
  const pb = b.split("-").map(Number);
  const da = Date.UTC(pa[0], pa[1] - 1, pa[2]);
  const db = Date.UTC(pb[0], pb[1] - 1, pb[2]);
  return Math.round((db - da) / 86_400_000);
}

/**
 * Advance the streak for "the app was opened today".
 * - same day            → unchanged
 * - next day            → +1
 * - gap ≥ 2 days / back  → reset to 1 (today still counts as a visit)
 */
export function rolloverStreak(state: CatState, today: string): CatState {
  if (state.lastActiveDay === today) return state;

  let streak: number;
  if (state.lastActiveDay == null) {
    streak = 1;
  } else {
    const gap = daysBetween(state.lastActiveDay, today);
    streak = gap === 1 ? state.streak + 1 : 1;
  }
  return {
    ...state,
    streak,
    bestStreak: Math.max(state.bestStreak, streak),
    lastActiveDay: today,
  };
}

// --- Growth & skins --------------------------------------------------------

/** Cat grows as the streak climbs. */
export function stageForStreak(streak: number): CatStage {
  if (streak >= 14) return "wizard";
  if (streak >= 7) return "bigcat";
  if (streak >= 3) return "cat";
  return "kitten";
}

/** Skin → best-streak day it unlocks at. "classic" is always available. */
export const SKIN_MILESTONES: { skin: CatSkin; at: number }[] = [
  { skin: "classic", at: 0 },
  { skin: "tabby", at: 3 },
  { skin: "sakura", at: 5 },
  { skin: "tuxedo", at: 7 },
  { skin: "mint", at: 10 },
  { skin: "calico", at: 14 },
  { skin: "snow", at: 21 },
  { skin: "void", at: 30 },
  { skin: "ember", at: 45 },
  { skin: "golden", at: 60 },
];

export function skinsUnlocked(bestStreak: number): CatSkin[] {
  return SKIN_MILESTONES.filter((m) => bestStreak >= m.at).map((m) => m.skin);
}

/** Clamp a (possibly stale) skin choice to what's currently unlocked. */
export function resolveSkin(skin: CatSkin, bestStreak: number): CatSkin {
  return skinsUnlocked(bestStreak).includes(skin) ? skin : "classic";
}

// --- Achievements (derived purely from best_streak — no storage) ------------

export interface Achievement {
  id: string; // i18n key suffix: cat.achievements.<id>
  at: number; // best-streak threshold
  icon: string;
}

/** Visit-streak achievements, ascending. Thresholds line up with skin/hat
 *  unlocks where one exists, so the reward is visible in the same moment. */
export const ACHIEVEMENTS: Achievement[] = [
  { id: "streak-1", at: 1, icon: "🐾" },
  { id: "streak-3", at: 3, icon: "🌱" },
  { id: "streak-5", at: 5, icon: "🌸" },
  { id: "streak-7", at: 7, icon: "🧶" },
  { id: "streak-10", at: 10, icon: "🍃" },
  { id: "streak-14", at: 14, icon: "🧙" },
  { id: "streak-21", at: 21, icon: "❄️" },
  { id: "streak-30", at: 30, icon: "👑" },
  { id: "streak-45", at: 45, icon: "🎧" },
  { id: "streak-60", at: 60, icon: "🏆" },
  { id: "streak-100", at: 100, icon: "💯" },
];

export function achievementsUnlocked(bestStreak: number): Achievement[] {
  return ACHIEVEMENTS.filter((a) => bestStreak >= a.at);
}

/** Achievements whose threshold was crossed going prevBest → newBest. */
export function newlyUnlocked(prevBest: number, newBest: number): Achievement[] {
  return ACHIEVEMENTS.filter((a) => prevBest < a.at && newBest >= a.at);
}

// --- "Thought" picked from already-studied topics --------------------------

export interface CatThought {
  /** Stable id for anti-repeat: "{course}/{lesson}#{anchor}" per concept. */
  key: string;
  term: string;
  definition: string;
  link: { course_slug: string; lesson_slug: string; anchor: string };
}

/** Strip the lightest markdown and trim to a friendly bubble length. The server
 *  already truncates, but this keeps the bubble tidy if a definition is reused. */
export function plainDefinition(md: string, max = 160): string {
  const text = md
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/\*([^*]*)\*/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= max) return text;
  return text.slice(0, max).replace(/\s+\S*$/, "") + "…";
}

/** The "{course}/{lesson}" a thought belongs to (its key without the anchor). */
function lessonOf(key: string): string {
  return key.split("#")[0];
}

/**
 * Pick a "thought" about a topic the user has actually finished. The pool comes
 * straight from the server (`GET /api/cat/thoughts`): one entry per concept of
 * every **completed** lesson ("Урок пройден"), each with its lesson section
 * (`anchor`) and a short definition parsed from the lesson markdown.
 *
 * Selection is **two-stage** so it feels like jumping between topics rather than
 * walking a list: pick a random *lesson* first (every lesson gets equal weight,
 * regardless of how many concepts it has — so a big lesson doesn't dominate),
 * then a random concept within it. It avoids the lesson shown last and skips
 * recently shown concept keys, so repeated clicks keep moving across the
 * curriculum. Returns null when nothing is completed (the widget then shows a
 * friendly nudge). Deterministic per seed.
 */
export function pickThought(
  thoughts: CatThoughtApi[],
  recentKeys: string[],
  seed: number,
): CatThought | null {
  if (!thoughts.length) return null;

  // De-dup by key (defensive — the server already yields one per concept).
  const byKey = new Map<string, CatThoughtApi>();
  for (const t of thoughts) if (!byKey.has(t.key)) byKey.set(t.key, t);
  const unique = [...byKey.values()];

  // Anti-repeat: drop recently shown concepts, unless that would empty the pool.
  const recent = new Set(recentKeys);
  const fresh = unique.filter((t) => !recent.has(t.key));
  const pool = fresh.length ? fresh : unique;

  // Group the candidate concepts by lesson.
  const byLesson = new Map<string, CatThoughtApi[]>();
  for (const t of pool) {
    const lk = lessonOf(t.key);
    (byLesson.get(lk) ?? byLesson.set(lk, []).get(lk)!).push(t);
  }

  // Stage 1 — choose a lesson, avoiding the one shown last when we can.
  const lastLesson = recentKeys.length
    ? lessonOf(recentKeys[recentKeys.length - 1])
    : null;
  let lessons = [...byLesson.keys()];
  const others = lessons.filter((lk) => lk !== lastLesson);
  if (others.length) lessons = others;

  const rng = makeRng(seed >>> 0 || 1);
  const lesson = lessons[Math.floor(rng() * lessons.length)];

  // Stage 2 — choose a concept within that lesson.
  const concepts = byLesson.get(lesson)!;
  const chosen = concepts[Math.floor(rng() * concepts.length)];
  return {
    key: chosen.key,
    term: chosen.term,
    definition: chosen.definition,
    link: {
      course_slug: chosen.course_slug,
      lesson_slug: chosen.lesson_slug,
      anchor: chosen.anchor,
    },
  };
}
