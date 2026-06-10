/**
 * Deterministic per-course accent. Gives each course card a stable colour tile
 * so the catalogue reads as a set of distinct topics rather than a wall of
 * identical cards. Hues are mid-tone so they hold up on both light and dark.
 */
const PALETTE = [
  { fg: "#4f46e5", bg: "#eef0fe" }, // indigo
  { fg: "#0d9488", bg: "#d9f3ee" }, // teal
  { fg: "#c2410c", bg: "#fdebe0" }, // rust
  { fg: "#7c3aed", bg: "#f1e9fe" }, // violet
  { fg: "#0369a1", bg: "#e0f0fb" }, // blue
  { fg: "#b45309", bg: "#fbf0db" }, // amber
  { fg: "#be123c", bg: "#fde4ea" }, // rose
  { fg: "#15803d", bg: "#e3f5ea" }, // green
  { fg: "#6d28d9", bg: "#ede9fe" }, // purple
  { fg: "#0e7490", bg: "#ddf2f6" }, // cyan
];

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function courseAccent(slug: string): { fg: string; bg: string } {
  return PALETTE[hash(slug) % PALETTE.length];
}

/** First letters of a title, for the course tile glyph (e.g. "Python Core" → "PC"). */
export function courseInitials(title: string): string {
  const words = title.replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
