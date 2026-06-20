import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CODE_THEME_DARK,
  CODE_THEME_LIGHT,
  getHighlighter,
} from "../lib/shiki";
import { useTheme } from "../theme/ThemeContext";
import { IconCheck, IconCopy } from "./icons";

const ALIASES: Record<string, string> = {
  py: "python",
  pycon: "python",
  console: "bash",
  sh: "bash",
  shell: "bash",
};

const SUPPORTED = new Set(["python", "bash", "json", "text", "c", "sql"]);

/** A copy-to-clipboard button, shown on hover/focus over a code block. */
function CopyButton({ code }: { code: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(id);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      /* clipboard blocked — nothing to do */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? t("common.copied") : t("common.copy")}
      title={copied ? t("common.copied") : t("common.copy")}
      className={`absolute right-2 top-2 z-10 inline-flex items-center gap-1 rounded-lg border border-border bg-surface/90 px-2 py-1 text-xs font-semibold shadow-card backdrop-blur transition-opacity focus:opacity-100 focus-visible:opacity-100 group-hover:opacity-100 sm:opacity-0 ${
        copied ? "text-celebrate" : "text-muted hover:text-ink"
      }`}
    >
      {copied ? (
        <IconCheck className="h-3.5 w-3.5" />
      ) : (
        <IconCopy className="h-3.5 w-3.5" />
      )}
      <span className="hidden sm:inline">
        {copied ? t("common.copied") : t("common.copy")}
      </span>
    </button>
  );
}

/**
 * Highlights a code block with Shiki (VS Code's tokenizer). Re-highlights when
 * the app theme flips so code matches light/dark. Renders raw code first so
 * there's never a blank flash. A copy button overlays the top-right corner.
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

  return (
    <div className="group relative">
      <CopyButton code={code} />
      {html ? (
        <div className="codeblock" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <pre className="codeblock-fallback">{code}</pre>
      )}
    </div>
  );
}
