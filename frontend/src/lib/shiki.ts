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

// VS Code's own default themes (light-plus / dark-plus), picked by app theme.
export const CODE_THEME_LIGHT = "light-plus";
export const CODE_THEME_DARK = "dark-plus";

export function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: [CODE_THEME_LIGHT, CODE_THEME_DARK],
      langs: ["python", "bash", "json", "text", "c", "sql"],
    });
  }
  return highlighterPromise;
}
