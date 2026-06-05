// Pure, deterministic quiz generation for the glossary.
//
// The client already has every term + definition (from /api/glossary); this
// module turns them — weighted by the user's per-term stats — into a
// multiple-choice quiz. All randomness flows through an injectable `rng` so the
// output is fully testable. No React, no network here.
import type { GlossaryTerm, GlossaryTermStat } from "../api/types";

export type QuestionType = "def-to-term" | "term-to-def";
export type SelectionMode = "smart" | "weak" | "mistakes" | "random";

export interface QuizConfig {
  categories: string[]; // selected category slugs; empty = all
  count: number; // requested number of questions
  types: QuestionType[]; // allowed question types (1 or 2)
  mode: SelectionMode;
}

export interface QuizOption {
  slug: string;
  label: string; // a term name (def-to-term) or a truncated definition
  correct: boolean;
}

export interface QuizQuestion {
  id: string;
  type: QuestionType;
  termSlug: string;
  term: string; // canonical term name (shown as feedback)
  definition: string; // full short_md (shown as feedback)
  prompt: string; // what to render as the question
  promptIsMarkdown: boolean; // true when the prompt is a definition
  options: QuizOption[]; // 4, shuffled, exactly one correct
}

export type StatMap = Record<string, GlossaryTermStat>;

const RECENT_MS = 10 * 60 * 1000; // demote terms seen in the last 10 minutes
const N_OPTIONS = 4;

// --- PRNG (mulberry32) — seedable for deterministic tests ------------------
export function makeRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(arr: T[], rng: () => number): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// --- Term buckets + selection weight ---------------------------------------
export type Bucket = "new" | "weak" | "learning" | "mastered";

export function bucketOf(stat: GlossaryTermStat | undefined): Bucket {
  if (!stat || stat.seen === 0) return "new";
  if (stat.mastered) return "mastered";
  if (!stat.last_correct || stat.correct / stat.seen < 0.6) return "weak";
  return "learning";
}

function weightOf(
  stat: GlossaryTermStat | undefined,
  mode: SelectionMode,
  now: number,
): number {
  const b = bucketOf(stat);
  if (mode === "random") return 1;
  if (mode === "mistakes") return stat && !stat.last_correct ? 1 : 0;
  if (mode === "weak") return b === "new" || b === "weak" ? 1 : 0;
  // smart
  const base = { new: 4, weak: 4, learning: 2, mastered: 0.5 }[b];
  const recent =
    stat && now - new Date(stat.last_seen_at).getTime() < RECENT_MS ? 0.3 : 1;
  return base * recent;
}

// Weighted sampling without replacement.
function weightedSample(
  terms: GlossaryTerm[],
  weight: (t: GlossaryTerm) => number,
  count: number,
  rng: () => number,
): GlossaryTerm[] {
  const items = terms
    .map((t) => ({ t, w: weight(t) }))
    .filter((it) => it.w > 0);
  const chosen: GlossaryTerm[] = [];
  while (chosen.length < count && items.length > 0) {
    const total = items.reduce((s, it) => s + it.w, 0);
    let r = rng() * total;
    let idx = 0;
    while (idx < items.length - 1 && r >= items[idx].w) {
      r -= items[idx].w;
      idx++;
    }
    chosen.push(items[idx].t);
    items.splice(idx, 1);
  }
  return chosen;
}

// --- Definition truncation (for term-to-def option labels) -----------------
export function truncateDefinition(md: string, max = 120): string {
  const plain = md
    .replace(/```[\s\S]*?```/g, "")
    .replace(/[*`#>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const firstSentence = plain.match(/^.*?[.!?](\s|$)/)?.[0]?.trim();
  const base = firstSentence && firstSentence.length >= 30 ? firstSentence : plain;
  return base.length > max ? base.slice(0, max).trimEnd() + "…" : base;
}

function pickDistractors(
  subject: GlossaryTerm,
  pool: GlossaryTerm[],
  allTerms: GlossaryTerm[],
  n: number,
  rng: () => number,
): GlossaryTerm[] {
  const exclude = subject.slug;
  const sameCat = pool.filter(
    (t) => t.slug !== exclude && t.category === subject.category,
  );
  const otherCat = pool.filter(
    (t) => t.slug !== exclude && t.category !== subject.category,
  );
  const global = allTerms.filter((t) => t.slug !== exclude);
  const ordered = [
    ...shuffle(sameCat, rng),
    ...shuffle(otherCat, rng),
    ...shuffle(global, rng),
  ];
  const out: GlossaryTerm[] = [];
  const seen = new Set<string>([exclude]);
  for (const t of ordered) {
    if (seen.has(t.slug)) continue;
    seen.add(t.slug);
    out.push(t);
    if (out.length === n) break;
  }
  return out;
}

function buildQuestion(
  subject: GlossaryTerm,
  pool: GlossaryTerm[],
  allTerms: GlossaryTerm[],
  types: QuestionType[],
  rng: () => number,
): QuizQuestion {
  const type =
    types.length === 1 ? types[0] : types[Math.floor(rng() * types.length)];
  const distractors = pickDistractors(subject, pool, allTerms, N_OPTIONS - 1, rng);

  const optionFor = (t: GlossaryTerm, correct: boolean): QuizOption => ({
    slug: t.slug,
    label: type === "def-to-term" ? t.term : truncateDefinition(t.short_md),
    correct,
  });
  const options = shuffle(
    [optionFor(subject, true), ...distractors.map((d) => optionFor(d, false))],
    rng,
  );

  return {
    id: `${subject.slug}:${type}`,
    type,
    termSlug: subject.slug,
    term: subject.term,
    definition: subject.short_md,
    prompt: type === "def-to-term" ? subject.short_md : subject.term,
    promptIsMarkdown: type === "def-to-term",
    options,
  };
}

export interface BuildOpts {
  rng?: () => number;
  now?: number;
}

/** Build a quiz from the full term list + the user's stats, per config. */
export function buildQuiz(
  allTerms: GlossaryTerm[],
  stats: StatMap,
  config: QuizConfig,
  opts: BuildOpts = {},
): QuizQuestion[] {
  const rng = opts.rng ?? Math.random;
  const now = opts.now ?? Date.now();
  const types = config.types.length ? config.types : ["def-to-term" as const];

  const cats = new Set(config.categories);
  const pool =
    cats.size === 0
      ? allTerms
      : allTerms.filter((t) => cats.has(t.category));
  if (pool.length === 0) return [];

  const subjects = weightedSample(
    pool,
    (t) => weightOf(stats[t.slug], config.mode, now),
    config.count,
    rng,
  );
  return subjects.map((s) => buildQuestion(s, pool, allTerms, types, rng));
}

/** How many terms are eligible as quiz subjects for a given config (for the
 * pool-size hint and to disable "start" when nothing matches). */
export function eligibleCount(
  allTerms: GlossaryTerm[],
  stats: StatMap,
  config: QuizConfig,
  now: number = Date.now(),
): number {
  const cats = new Set(config.categories);
  const pool =
    cats.size === 0 ? allTerms : allTerms.filter((t) => cats.has(t.category));
  return pool.filter((t) => weightOf(stats[t.slug], config.mode, now) > 0).length;
}

/** Turn a finished quiz into the payload for POST /glossary/quiz/result. */
export function toResultItems(
  answers: { termSlug: string; correct: boolean }[],
): { term_slug: string; correct: boolean }[] {
  return answers.map((a) => ({ term_slug: a.termSlug, correct: a.correct }));
}
