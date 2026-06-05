/**
 * Slugify a heading the same way the content's `anchor` values are produced,
 * so "Back to theory" deep-links land on the right section.
 *
 * Rule (verified against content/courses/python-core/metadata.json):
 *   lowercase → drop punctuation (keep letters/digits/spaces/dash, incl.
 *   Cyrillic) → collapse whitespace to single dashes.
 *
 * e.g. "GIL и потоки: CPU-bound vs IO-bound" → "gil-и-потоки-cpu-bound-vs-io-bound"
 */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}
