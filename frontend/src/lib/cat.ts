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
  /** Stable id for anti-repeat (term slug, or a concept-anchor for fallbacks). */
  key: string;
  term: string;
  definition: string;
  link: { course_slug: string; lesson_slug: string; anchor: string };
}

/** Normalise to lowercase tokens (latin + cyrillic), ё→е, drop punctuation. */
function normTokens(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^a-z0-9а-я]+/gi, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

/** Match phrases for a glossary term: its name (with/without the parenthetical),
 *  the parenthetical itself, and any aliases. Each as a token array. */
function termPhrases(t: GlossaryTerm): string[][] {
  const raw: string[] = [t.term, t.term.replace(/\([^)]*\)/g, " ")];
  const paren = t.term.match(/\(([^)]+)\)/);
  if (paren) raw.push(paren[1]);
  for (const a of t.aliases ?? []) raw.push(a);
  return raw
    .map(normTokens)
    .filter((toks) => toks.length > 0 && toks.join("").length >= 3);
}

/** True if `needle` appears as a contiguous run of tokens in `hay`. */
function hasContiguous(hay: string[], needle: string[]): boolean {
  if (!needle.length || needle.length > hay.length) return false;
  for (let i = 0; i + needle.length <= hay.length; i++) {
    let ok = true;
    for (let j = 0; j < needle.length; j++) {
      if (hay[i + j] !== needle[j]) {
        ok = false;
        break;
      }
    }
    if (ok) return true;
  }
  return false;
}

/** Best glossary term whose name/alias phrase occurs in a concept title (most
 *  specific match wins), or null. Token-contiguous matching avoids false hits
 *  like "is" inside "history". */
export function matchConceptToTerm(
  conceptTitle: string,
  terms: GlossaryTerm[],
): GlossaryTerm | null {
  const hay = normTokens(conceptTitle);
  let best: GlossaryTerm | null = null;
  let bestScore = 0;
  for (const t of terms) {
    for (const phrase of termPhrases(t)) {
      if (hasContiguous(hay, phrase)) {
        const score = phrase.join("").length + phrase.length * 2;
        if (score > bestScore) {
          bestScore = score;
          best = t;
        }
      }
    }
  }
  return best;
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
 * Pick a "thought" about a topic the user has actually finished. Source: the
 * concepts of **completed** lessons ("Урок пройден" → `lesson.completed`); each
 * concept gives a precise lesson section (its `anchor`) and is matched to a
 * glossary term for a real definition. Picks at random, skipping the recently
 * shown keys so repeated clicks vary. Returns null when no lesson is completed
 * (the widget then shows a friendly nudge). Deterministic per seed.
 */
export function pickThought(
  terms: GlossaryTerm[],
  progress: ProgressOverviewOut | undefined,
  recentKeys: string[],
  seed: number,
): CatThought | null {
  if (!progress) return null;

  const matched: CatThought[] = []; // concept matched to a glossary term (has a definition)
  const fallback: CatThought[] = []; // completed-lesson concept with no term match (title only)

  for (const c of progress.courses) {
    for (const l of c.lessons) {
      if (!l.completed) continue;
      for (const cn of l.concepts) {
        const link = { course_slug: c.slug, lesson_slug: l.slug, anchor: cn.anchor };
        const term = terms.length ? matchConceptToTerm(cn.title, terms) : null;
        if (term) {
          matched.push({
            key: term.slug,
            term: term.term,
            definition: plainDefinition(term.short_md),
            link,
          });
        } else {
          fallback.push({
            key: `${c.slug}/${l.slug}#${cn.anchor}`,
            term: cn.title,
            definition: "",
            link,
          });
        }
      }
    }
  }

  // Prefer real definitions; fall back to bare concept titles only if needed.
  const pool = matched.length ? matched : fallback;
  if (!pool.length) return null;

  // De-dup by key (a term can match concepts across several lessons).
  const byKey = new Map<string, CatThought>();
  for (const cand of pool) if (!byKey.has(cand.key)) byKey.set(cand.key, cand);
  const unique = [...byKey.values()];

  // Anti-repeat: drop recently shown keys, unless that would empty the pool.
  const recent = new Set(recentKeys);
  const filtered = unique.filter((c) => !recent.has(c.key));
  const choices = filtered.length ? filtered : unique;

  const rng = makeRng(seed >>> 0 || 1);
  return choices[Math.floor(rng() * choices.length)];
}
