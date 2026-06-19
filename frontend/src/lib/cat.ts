// Pure, deterministic logic for the corner "tamagotchi" cat. No React, no
// network, no localStorage here — just functions over plain data so they're
// trivially testable (see cat.test.ts). The hook (cat/useCat.ts) owns side
// effects (persistence, timers); the widget owns rendering.
import type { GlossaryTerm, PetState, ProgressOverviewOut } from "../api/types";
import { makeRng } from "./glossaryQuiz";

// --- Persistent state ------------------------------------------------------

export type CatStage = "kitten" | "cat" | "bigcat" | "wizard";
export type CatSkin = "classic" | "tabby" | "tuxedo" | "calico" | "void";

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
  { skin: "tuxedo", at: 7 },
  { skin: "calico", at: 14 },
  { skin: "void", at: 30 },
];

export function skinsUnlocked(bestStreak: number): CatSkin[] {
  return SKIN_MILESTONES.filter((m) => bestStreak >= m.at).map((m) => m.skin);
}

/** Clamp a (possibly stale) skin choice to what's currently unlocked. */
export function resolveSkin(skin: CatSkin, bestStreak: number): CatSkin {
  return skinsUnlocked(bestStreak).includes(skin) ? skin : "classic";
}

// --- "Thought" picked from already-studied topics --------------------------

export interface CatThought {
  term: string;
  definition: string;
  link: { course_slug: string; lesson_slug: string; anchor: string };
}

/** Strip the lightest markdown and trim to a friendly bubble length. */
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

/**
 * Pick one glossary term whose theory the user has actually been through, so
 * the cat "remembers" something real. A lesson counts as studied once it's
 * marked done ("Урок пройден") OR the user has answered a question on it;
 * mastered lessons are preferred. Returns null when nothing qualifies (the
 * widget then shows a friendly nudge to study first). Deterministic per seed.
 */
export function pickThought(
  terms: GlossaryTerm[],
  progress: ProgressOverviewOut | undefined,
  seed: number,
): CatThought | null {
  if (!terms.length || !progress) return null;

  const studied = new Set<string>();
  const mastered = new Set<string>();
  for (const c of progress.courses) {
    for (const l of c.lessons) {
      const key = `${c.slug}/${l.slug}`;
      if (l.completed || l.attempted_concepts > 0) studied.add(key);
      if (l.mastered_concepts > 0) mastered.add(key);
    }
  }
  if (!studied.size) return null;

  // Build candidate list, preferring mastered lessons.
  const candidates: { term: GlossaryTerm; pref: number }[] = [];
  for (const t of terms) {
    const link = t.links.find((l) => studied.has(`${l.course_slug}/${l.lesson_slug}`));
    if (!link) continue;
    const pref = mastered.has(`${link.course_slug}/${link.lesson_slug}`) ? 1 : 0;
    candidates.push({ term: t, pref });
  }
  if (!candidates.length) return null;

  const masteredCands = candidates.filter((c) => c.pref === 1);
  const pool = masteredCands.length ? masteredCands : candidates;

  const rng = makeRng(seed >>> 0 || 1);
  const chosen = pool[Math.floor(rng() * pool.length)].term;
  const link =
    chosen.links.find(
      (l) =>
        mastered.has(`${l.course_slug}/${l.lesson_slug}`) ||
        studied.has(`${l.course_slug}/${l.lesson_slug}`),
    ) ?? chosen.links[0];

  return {
    term: chosen.term,
    definition: plainDefinition(chosen.short_md),
    link: {
      course_slug: link.course_slug,
      lesson_slug: link.lesson_slug,
      anchor: link.anchor,
    },
  };
}
