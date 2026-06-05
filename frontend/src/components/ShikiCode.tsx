import { useEffect, useState } from "react";
import {
  CODE_THEME_DARK,
  CODE_THEME_LIGHT,
  getHighlighter,
} from "../lib/shiki";
import { useTheme } from "../theme/ThemeContext";

const ALIASES: Record<string, string> = {
  py: "python",
  pycon: "python",
  console: "bash",
  sh: "bash",
  shell: "bash",
};

const SUPPORTED = new Set(["python", "bash", "json", "text", "c", "sql"]);

/**
 * Highlights a code block with Shiki (VS Code's tokenizer). Re-highlights when
 * the app theme flips so code matches light/dark. Renders raw code first so
 * there's never a blank flash.
 */
export function ShikiCode({ code, lang }: { code: string; lang: string }) {
  const { theme } = useTheme();
  const [html, setHtml] = useState<string | null>(null);
  const shikiTheme = theme === "dark" ? CODE_THEME_DARK : CODE_THEME_LIGHT;

  useEffect(() => {
    let alive = true;
    const resolved = ALIASES[lang] ?? lang;
    const finalLang = SUPPORTED.has(resolved) ? resolved : "text";

    getHighlighter()
      .then((hl) => {
        if (!alive) return;
        setHtml(hl.codeToHtml(code, { lang: finalLang, theme: shikiTheme }));
      })
      .catch(() => {
        /* keep the plain fallback */
      });

    return () => {
      alive = false;
    };
  }, [code, lang, shikiTheme]);

  if (html) {
    return <div className="codeblock" dangerouslySetInnerHTML={{ __html: html }} />;
  }
  return <pre className="codeblock-fallback">{code}</pre>;
}
