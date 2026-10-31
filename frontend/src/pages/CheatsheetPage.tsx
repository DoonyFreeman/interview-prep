import { useLayoutEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { EmptyState } from "../components/EmptyState";
import { IconArticle } from "../components/icons";
import { Markdown } from "../components/Markdown";
import { getCheatsheet, getCheatsheetSections } from "../lib/cheatsheets";
import "../components/cheatsheets.css";

export function CheatsheetPage() {
  const { slug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const sheet = getCheatsheet(slug);
  const sections = useMemo(() => getCheatsheetSections(sheet?.markdown ?? ""), [sheet]);

  // A sheet can be opened from the bottom of a catalog or a long lesson.
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  if (!sheet) {
    return (
      <div className="cheatsheet-reader">
        <h1 className="mb-6 font-display text-2xl font-bold text-ink">{t("cheatsheets.title")}</h1>
        <EmptyState
          icon={<IconArticle className="h-6 w-6 text-primary" />}
          title={t("cheatsheets.notFoundTitle")}
          hint={t("cheatsheets.notFoundDescription")}
        >
          <Link to="/cheatsheets" className="cheatsheet-action cheatsheet-action-primary">
            {t("cheatsheets.backToLibrary")}
          </Link>
        </EmptyState>
      </div>
    );
  }

  return (
    <article className="cheatsheet-reader">
      <div className="cheatsheet-reader-toolbar">
        <Link to="/cheatsheets" className="cheatsheet-back-link">
          <span aria-hidden="true">←</span> {t("cheatsheets.backToLibrary")}
        </Link>
        <a href={sheet.pdfUrl} download className="cheatsheet-action cheatsheet-action-primary">
          {t("cheatsheets.downloadPdf")}
        </a>
      </div>
      <header className="cheatsheet-reader-header">
        <div className="cheatsheet-reader-meta">
          <span>{t(`cheatsheets.groups.${sheet.category}`)}</span>
          <span aria-hidden="true">/</span>
          <span>{t("cheatsheets.pageCount", { count: sheet.pages })}</span>
        </div>
        <h1 className="font-display text-3xl font-bold text-ink sm:text-4xl">{sheet.title}</h1>
        <p className="mt-3 max-w-2xl text-muted">{sheet.description}</p>
      </header>
      <div className="cheatsheet-section-grid">
        {sections.map((section, index) => (
          <section key={section.anchor} className="cheatsheet-section" aria-labelledby={section.title ? section.anchor : undefined}>
            {section.title ? (
              <div className="cheatsheet-section-heading">
                <span className="cheatsheet-section-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <h2 id={section.anchor} className="font-display">{section.title}</h2>
              </div>
            ) : null}
            <Markdown markdown={section.markdown} />
          </section>
        ))}
      </div>
    </article>
  );
}
