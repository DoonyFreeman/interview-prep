import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useGlossary } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { EmptyState } from "../components/EmptyState";
import type { GlossaryTerm } from "../api/types";

export function SlangPage() {
  const { t } = useTranslation();
  const slang = useGlossary(null, "", "slang");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const terms = slang.data?.terms ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return terms;
    return terms.filter(
      (term) =>
        term.term.toLowerCase().includes(q) ||
        term.slug.includes(q) ||
        term.aliases.some((a) => a.toLowerCase().includes(q)) ||
        term.short_md.toLowerCase().includes(q),
    );
  }, [slang.data, query]);

  // Group by first letter, sorted alphabetically (locale-aware for Cyrillic).
  const groups = useMemo(() => {
    const byLetter = new Map<string, GlossaryTerm[]>();
    for (const term of filtered) {
      const letter = (term.term[0] || "#").toUpperCase();
      const list = byLetter.get(letter) ?? [];
      list.push(term);
      byLetter.set(letter, list);
    }
    return [...byLetter.entries()]
      .sort((a, b) => a[0].localeCompare(b[0], "ru"))
      .map(([letter, terms]) => ({
        letter,
        terms: terms
          .slice()
          .sort((a, b) => a.term.localeCompare(b.term, "ru")),
      }));
  }, [filtered]);

  if (slang.isLoading) return <PageLoader label={t("common.loading")} />;
  if (slang.isError || !slang.data)
    return <p className="text-danger">{t("common.error")}</p>;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink">
            {t("slang.title")}
          </h1>
          <p className="mt-1 text-muted">
            {t("slang.subtitle", { count: slang.data.count })}
          </p>
        </div>
        <Link
          to="/slang/quiz"
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-fg shadow-card transition-[background-color] hover:bg-primary-strong"
        >
          🎯 {t("slang.quizCta")}
        </Link>
      </div>

      <div className="sticky top-15 z-10 -mx-4 mt-5 mb-6 bg-bg/80 px-4 py-3 backdrop-blur">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("slang.searchPlaceholder")}
          className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-ink outline-none placeholder:text-faint focus:border-primary"
        />
      </div>

      {groups.length === 0 ? (
        <EmptyState icon="🔍" title={t("slang.noResults")} />
      ) : (
        <div className="space-y-8">
          {groups.map(({ letter, terms }) => (
            <section key={letter} className="flex gap-4">
              <div className="w-8 shrink-0 pt-1 text-2xl font-black text-primary/40">
                {letter}
              </div>
              <div className="min-w-0 flex-1 space-y-3">
                {terms.map((term) => (
                  <div
                    key={term.slug}
                    id={term.slug}
                    className="scroll-mt-24 rounded-2xl border border-border bg-surface p-4 shadow-card"
                  >
                    <h3 className="font-display font-bold text-ink">{term.term}</h3>
                    {term.aliases.length > 0 && (
                      <p className="text-xs text-faint">{term.aliases.join(" · ")}</p>
                    )}
                    <p className="mt-1 text-sm leading-relaxed text-muted">
                      {term.short_md}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
