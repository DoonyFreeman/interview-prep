import { Fragment, type ReactNode } from "react";

export interface MatchSegment {
  text: string;
  match: boolean;
}

/**
 * Split `text` into segments, marking the parts that match `query`
 * (case-insensitive, all occurrences). Pure + side-effect-free so it's easy to
 * unit-test; the React wrapper below renders the matched segments as <mark>.
 */
export function splitMatch(text: string, query: string): MatchSegment[] {
  const q = query.trim();
  if (!q) return [{ text, match: false }];

  const segments: MatchSegment[] = [];
  const hay = text.toLowerCase();
  const needle = q.toLowerCase();
  let from = 0;

  for (;;) {
    const at = hay.indexOf(needle, from);
    if (at === -1) {
      if (from < text.length) segments.push({ text: text.slice(from), match: false });
      break;
    }
    if (at > from) segments.push({ text: text.slice(from, at), match: false });
    segments.push({ text: text.slice(at, at + needle.length), match: true });
    from = at + needle.length;
  }

  return segments;
}

/**
 * Render `text` with the substrings matching `query` wrapped in a soft accent
 * <mark>. Used in dictionary search so users see *why* a result matched.
 */
export function Highlight({ text, query }: { text: string; query: string }): ReactNode {
  const segments = splitMatch(text, query);
  return segments.map((seg, i) =>
    seg.match ? (
      <mark
        key={i}
        className="rounded bg-accent-soft px-0.5 text-accent"
      >
        {seg.text}
      </mark>
    ) : (
      <Fragment key={i}>{seg.text}</Fragment>
    ),
  );
}
