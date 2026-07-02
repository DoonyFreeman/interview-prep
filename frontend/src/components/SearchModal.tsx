import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useSearch } from "../api/hooks";
import { Highlight } from "../lib/highlight";
import { IconSearch } from "./icons";

/**
 * Global lesson search: a magnifier in the header + Cmd/Ctrl+K open a
 * command-palette overlay. Results come server-ranked from /api/search; a row
 * click deep-links to the lesson (and its H2 anchor for section hits).
 */
export function SearchModal() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [query, setQuery] = useState(""); // debounced
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const search = useSearch(query);
  const results = query.trim().length >= 2 ? (search.data?.results ?? []) : [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Cmd/Ctrl+K toggles even while typing — standard palette behavior.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Debounce input → query; reset selection on each new query.
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(input);
      setActive(0);
    }, 200);
    return () => clearTimeout(id);
  }, [input]);

  const close = () => {
    setOpen(false);
    setInput("");
    setQuery("");
    setActive(0);
  };

  const go = (r: (typeof results)[number]) => {
    close();
    navigate(
      `/courses/${r.course_slug}/lessons/${r.lesson_slug}` +
        (r.anchor ? `#${encodeURIComponent(r.anchor)}` : ""),
    );
  };

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") close();
    if (!results.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next =
        e.key === "ArrowDown"
          ? Math.min(active + 1, results.length - 1)
          : Math.max(active - 1, 0);
      setActive(next);
      listRef.current
        ?.children[next]?.scrollIntoView({ block: "nearest" });
    }
    if (e.key === "Enter" && results[active]) go(results[active]);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title={t("search.title")}
        aria-label={t("search.title")}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-ink"
      >
        <IconSearch className="h-4 w-4" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={close}
          >
            <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" />
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label={t("search.title")}
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", stiffness: 420, damping: 30 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-pop"
            >
              <div className="flex items-center gap-2.5 border-b border-border px-4">
                <IconSearch className="h-4 w-4 shrink-0 text-faint" />
                <input
                  autoFocus
                  type="search"
                  role="combobox"
                  aria-expanded={results.length > 0}
                  aria-controls="search-results"
                  aria-activedescendant={
                    results.length ? `search-result-${active}` : undefined
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onInputKey}
                  placeholder={t("search.placeholder")}
                  className="w-full bg-transparent py-3.5 text-base text-ink outline-none placeholder:text-faint sm:text-sm"
                />
                <kbd className="hidden shrink-0 rounded-md border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-faint sm:block">
                  Esc
                </kbd>
              </div>

              {query.trim().length >= 2 && (
                <div className="max-h-[55vh] overflow-y-auto overscroll-contain">
                  {results.length > 0 ? (
                    <ul ref={listRef} id="search-results" role="listbox" className="p-2">
                      {results.map((r, i) => (
                        <li
                          key={`${r.course_slug}/${r.lesson_slug}#${r.anchor}`}
                          id={`search-result-${i}`}
                          role="option"
                          aria-selected={i === active}
                        >
                          <button
                            onClick={() => go(r)}
                            onMouseMove={() => setActive(i)}
                            className={`block w-full rounded-xl px-3 py-2.5 text-left transition-colors ${
                              i === active ? "bg-primary-soft" : ""
                            }`}
                          >
                            <span className="block truncate text-xs text-faint">
                              {r.course_title} › {r.lesson_title}
                            </span>
                            <span
                              className={`block truncate text-sm font-semibold ${
                                i === active ? "text-primary" : "text-ink"
                              }`}
                            >
                              <Highlight
                                text={r.section_title || r.lesson_title}
                                query={query}
                              />
                            </span>
                            {r.snippet && (
                              <span className="mt-0.5 line-clamp-2 block text-xs text-muted">
                                <Highlight text={r.snippet} query={query} />
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    !search.isPending && (
                      <p className="px-4 py-8 text-center text-sm text-muted">
                        {t("search.noResults")}
                      </p>
                    )
                  )}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
