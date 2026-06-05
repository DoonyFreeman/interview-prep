import {
  createHighlighter,
  type Highlighter,
} from "shiki";

/**
 * Single shared Shiki highlighter. Shiki uses the same TextMate grammars as
 * VS Code, so code is tokenised word-by-word exactly like the editor. We load a
 * small set of languages the theory uses + the VS Code default light theme.
 */
let highlighterPromise: Promise<Highlighter> | null = null;

export const CODE_THEME = "light-plus";

export function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: [CODE_THEME],
      langs: ["python", "bash", "json", "text", "c", "sql"],
    });
  }
  return highlighterPromise;
}
