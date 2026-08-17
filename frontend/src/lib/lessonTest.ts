/**
 * Pure helpers for the lesson MCQ self-test runner: deterministic shuffling of
 * questions + their options, "review mistakes" filtering, and scoring. Kept free
 * of React so it can be unit-tested (see lessonTest.test.ts).
 *
 * Grading is client-side: the API ships each MCQ's correct_index (the options are
 * visible anyway and there's no LLM to protect), so we just shuffle and compare.
 */
import type { McqQuestion } from "../api/types";

export interface PreparedOption {
  label: string;
  correct: boolean;
}

/** Where a question came from — a mixed test spans lessons, so every question
 *  carries its own "back to theory" target and label. */
export interface McqOrigin {
  courseSlug: string;
  lessonSlug: string;
  courseTitle: string;
  lessonTitle: string;
}

export interface PreparedMcq extends McqOrigin {
  slug: string;
  type: string;
  text: string;
  conceptSlug: string;
  conceptTitle: string;
  anchor: string;
  explanationMd: string;
  options: PreparedOption[];
}

// The origin is optional on an Answer: scoring and result posting never need
// it, and it keeps callers that only care about correct/incorrect simple.
export interface Answer extends Partial<McqOrigin> {
  slug: string;
  conceptTitle: string;
  anchor: string;
  text: string;
  correct: boolean;
  /** Optional review detail captured at answer time (for the result screen). */
  pickedLabel?: string;
  correctLabel?: string;
  explanationMd?: string;
}

/** The lesson deep-link for a question, anchored at its concept's section.
 *  Empty when the origin is unknown — callers should skip the link then. */
export function theoryPath(q: Partial<McqOrigin> & { anchor?: string }): string {
  if (!q.courseSlug || !q.lessonSlug) return "";
  const base = `/courses/${q.courseSlug}/lessons/${q.lessonSlug}`;
  return q.anchor ? `${base}#${q.anchor}` : base;
}

/** Deterministic PRNG (mulberry32) so a seed reproduces the same quiz in tests. */
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

/** Fisher–Yates, non-mutating. */
export function shuffle<T>(arr: readonly T[], rng: () => number = Math.random): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export interface PrepareOptions {
  /** Restrict to these MCQ slugs (e.g. "review mistakes"). Empty/undefined = all. */
  onlySlugs?: Set<string> | string[];
  /** Cap the number of questions (after filtering). 0/undefined = no cap. */
  limit?: number;
  /** Seed the PRNG for reproducible order; omit for Math.random. */
  seed?: number;
  /** Origin for questions that don't carry their own (the per-lesson test,
   *  where the whole run comes from the lesson already named in the URL). */
  origin?: Partial<McqOrigin>;
}

/** Shuffle the question order and each question's options for a run. */
export function prepareTest(
  questions: readonly McqQuestion[],
  opts: PrepareOptions = {},
): PreparedMcq[] {
  const rng = opts.seed === undefined ? Math.random : makeRng(opts.seed);
  const only =
    opts.onlySlugs instanceof Set
      ? opts.onlySlugs
      : opts.onlySlugs
        ? new Set(opts.onlySlugs)
        : null;

  let pool = questions.filter((q) => !only || only.has(q.slug));
  pool = shuffle(pool, rng);
  if (opts.limit && opts.limit > 0) pool = pool.slice(0, opts.limit);

  const origin = opts.origin ?? {};
  return pool.map((q) => ({
    slug: q.slug,
    type: q.type,
    text: q.text,
    conceptSlug: q.concept_slug,
    conceptTitle: q.concept_title,
    anchor: q.anchor,
    explanationMd: q.explanation_md,
    courseSlug: q.course_slug || origin.courseSlug || "",
    lessonSlug: q.lesson_slug || origin.lessonSlug || "",
    courseTitle: q.course_title || origin.courseTitle || "",
    lessonTitle: q.lesson_title || origin.lessonTitle || "",
    options: shuffle(
      q.options.map((label, i) => ({ label, correct: i === q.correct_index })),
      rng,
    ),
  }));
}

/** Slugs the user got wrong last time (for the "review mistakes" entry point). */
export function mistakeSlugs(
  questions: readonly McqQuestion[],
  stats: { mcq_slug: string; last_correct: boolean; seen: number }[],
): string[] {
  const wrong = new Set(
    stats.filter((s) => s.seen > 0 && !s.last_correct).map((s) => s.mcq_slug),
  );
  return questions.filter((q) => wrong.has(q.slug)).map((q) => q.slug);
}

export function scorePct(answers: readonly Answer[]): number {
  if (answers.length === 0) return 0;
  const correct = answers.filter((a) => a.correct).length;
  return Math.round((correct / answers.length) * 100);
}

export function toResultItems(
  answers: readonly Answer[],
): { slug: string; correct: boolean }[] {
  return answers.map((a) => ({ slug: a.slug, correct: a.correct }));
}
