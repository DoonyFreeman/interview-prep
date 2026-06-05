import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useGlossary } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Markdown } from "../components/Markdown";
import type { GlossaryTerm } from "../api/types";

function categoryLabel(t: (k: string) => string, slug: string): string {
  const key = `glossary.cat.${slug}`;
  const label = t(key);
  return label === key ? slug : label;
}

function TermCard({ term }: { term: GlossaryTerm }) {
  const { t } = useTranslation();
  return (
    <article
      id={term.slug}
      className="scroll-mt-24 rounded-2xl border border-border bg-surface p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-lg font-bold text-ink">{term.term}</h3>
        {term.aliases.length > 0 && (
          <span className="text-sm text-faint">{term.aliases.join(" · ")}</span>
        )}
      </div>
      <div className="prose-sm mt-2">
        <Markdown markdown={term.short_md} />
      </div>
      {term.links.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {term.links.map((ln) => (
            <Link
              key={`${ln.course_slug}/${ln.lesson_slug}/${ln.anchor}`}
              to={`/courses/${ln.course_slug}/lessons/${ln.lesson_slug}#${ln.anchor}`}
              className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary hover:bg-primary-soft/70"
            >
              {t("glossary.toTheory")} →
            </Link>
          ))}
        </div>
      )}
    </article>
  );
}

export function GlossaryPage() {
  const { t } = useTranslation();
  const glossary = useGlossary(null, "");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const terms = glossary.data?.terms ?? [];
    const q = query.trim().toLowerCase();
    return terms.filter((term) => {
      if (category && term.category !== category) return false;
      if (!q) return true;
      return (
        term.term.toLowerCase().includes(q) ||
        term.slug.includes(q) ||
        term.aliases.some((a) => a.toLowerCase().includes(q)) ||
        term.short_md.toLowerCase().includes(q)
      );
    });
  }, [glossary.data, query, category]);

  // Group the filtered terms by category, preserving the canonical order.
  const groups = useMemo(() => {
    const order = glossary.data?.categories ?? [];
    const byCat = new Map<string, GlossaryTerm[]>();
    for (const term of filtered) {
      const list = byCat.get(term.category) ?? [];
      list.push(term);
      byCat.set(term.category, list);
    }
    return order
      .filter((c) => byCat.has(c))
      .map((c) => ({ category: c, terms: byCat.get(c)! }));
  }, [filtered, glossary.data]);

  if (glossary.isLoading) return <PageLoader label={t("common.loading")} />;
  if (glossary.isError || !glossary.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const categories = glossary.data.categories;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-ink">{t("glossary.title")}</h1>
      <p className="mt-1 text-muted">
        {t("glossary.subtitle", { count: glossary.data.count })}
      </p>

      {/* Search + category filter */}
      <div className="sticky top-15 z-10 -mx-4 mt-5 mb-6 bg-bg/80 px-4 py-3 backdrop-blur">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("glossary.searchPlaceholder")}
          className="w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm text-ink outline-none placeholder:text-faint focus:border-primary"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => setCategory(null)}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
              category === null
                ? "bg-primary text-primary-fg"
                : "border border-border bg-surface text-muted hover:bg-surface-2"
            }`}
          >
            {t("glossary.allCategories")}
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c === category ? null : c)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                category === c
                  ? "bg-primary text-primary-fg"
                  : "border border-border bg-surface text-muted hover:bg-surface-2"
              }`}
            >
              {categoryLabel(t, c)}
            </button>
          ))}
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center shadow-sm">
          <div className="text-3xl">🔍</div>
          <p className="mt-3 font-semibold text-ink">{t("glossary.noResults")}</p>
        </div>
      ) : (
        <div className="space-y-10">
          {groups.map(({ category: c, terms }) => (
            <section key={c}>
              <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-faint">
                {categoryLabel(t, c)} · {terms.length}
              </h2>
              <div className="space-y-4">
                {terms.map((term) => (
                  <TermCard key={term.slug} term={term} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
