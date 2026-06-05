import { useEffect, useState } from "react";
import { CODE_THEME, getHighlighter } from "../lib/shiki";

const ALIASES: Record<string, string> = {
  py: "python",
  pycon: "python",
  console: "bash",
  sh: "bash",
  shell: "bash",
};

const SUPPORTED = new Set(["python", "bash", "json", "text", "c", "sql"]);

/**
 * Highlights a code block with Shiki (VS Code's tokenizer). Renders the raw
 * code first, then swaps in the highlighted HTML once the highlighter is ready,
 * so there's never a blank flash.
 */
export function ShikiCode({ code, lang }: { code: string; lang: string }) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const resolved = ALIASES[lang] ?? lang;
    const finalLang = SUPPORTED.has(resolved) ? resolved : "text";

    getHighlighter()
      .then((hl) => {
        if (!alive) return;
        setHtml(hl.codeToHtml(code, { lang: finalLang, theme: CODE_THEME }));
      })
      .catch(() => {
        /* keep the plain fallback */
      });

    return () => {
      alive = false;
    };
  }, [code, lang]);

  if (html) {
    return <div className="codeblock" dangerouslySetInnerHTML={{ __html: html }} />;
  }
  return <pre className="codeblock-fallback">{code}</pre>;
}
