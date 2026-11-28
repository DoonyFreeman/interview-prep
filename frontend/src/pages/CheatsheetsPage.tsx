import { PrivateOpenspecDownloads } from "../components/PrivateOpenspecDownloads";
import { useAuth } from "../auth/AuthContext";
import { privateResumePath, usePrivateResume } from "../lib/privateResume";
import { useLayoutEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { IconArticle } from "../components/icons";
import { CHEATSHEETS, CHEATSHEET_GROUPS, RAG_CHEATSHEET_BUNDLE } from "../lib/cheatsheets";
import { interviewQuestions, pythonAiInterviewPath } from "../lib/pythonAiInterview";
import "../components/cheatsheets.css";

export function CheatsheetsPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const { data: resume } = usePrivateResume(token);

  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="cheatsheets-library">
      <header className="cheatsheets-library-header">
        <div className="cheatsheet-emblem" aria-hidden="true">
          <IconArticle className="h-6 w-6" />
        </div>
        <h1 className="font-display text-3xl font-bold text-ink sm:text-4xl">
          {t("cheatsheets.title")}
        </h1>
        <p className="mt-3 max-w-2xl text-muted">{t("cheatsheets.subtitle")}</p>
        <div className="cheatsheet-bundle-download mt-5">
          <a
            href="/cheatsheets/cheatsheets-all.pdf"
            download
            aria-describedby="cheatsheets-bundle-description"
            className="cheatsheet-action cheatsheet-action-primary"
          >
            {t("cheatsheets.downloadAllBundle")}
          </a>
          <p id="cheatsheets-bundle-description">{t("cheatsheets.allBundleDescription")}</p>
        </div>
        <PrivateOpenspecDownloads token={token} />
      </header>

      <div className="cheatsheet-groups">
        {Boolean(resume?.length) && (
          <article className="cheatsheet-catalog-card">
            <h2 className="font-display text-xl font-bold text-ink">Моё резюме</h2>
            <p className="cheatsheet-card-description">
              Разбор опыта, схемы работы сервисов и вопросы для собеседования.
            </p>
            <div className="cheatsheet-card-actions">
              <Link to={privateResumePath} className="cheatsheet-action cheatsheet-action-primary">
                Открыть <span aria-hidden="true">→</span>
              </Link>
            </div>
          </article>
        )}
        <article className="cheatsheet-catalog-card">
          <div className="cheatsheet-card-topline">
            <IconArticle className="h-5 w-5 text-primary" aria-hidden="true" />
            <span className="cheatsheet-page-count">
              {t("pythonAiInterview.questionCount", { count: interviewQuestions.length })}
            </span>
          </div>
          <h2 className="font-display text-xl font-bold text-ink">{t("pythonAiInterview.title")}</h2>
          <p className="cheatsheet-card-description">{t("pythonAiInterview.catalogDescription")}</p>
          <div className="cheatsheet-card-actions">
            <Link to={pythonAiInterviewPath} className="cheatsheet-action cheatsheet-action-primary">
              {t("pythonAiInterview.open")} <span aria-hidden="true">→</span>
            </Link>
          </div>
        </article>
        {CHEATSHEET_GROUPS.map((group) => (
          <section key={group.id} aria-labelledby={`cheatsheet-group-${group.id}`}>
            <div className="cheatsheet-group-header">
              <h2 id={`cheatsheet-group-${group.id}`} className="cheatsheet-group-title font-display">
                {t(group.labelKey)}
              </h2>
              {group.id === "rag" && (
                <div className="cheatsheet-bundle-download">
                  <a href={RAG_CHEATSHEET_BUNDLE.pdfUrl} download className="cheatsheet-action cheatsheet-action-primary">
                    {t("cheatsheets.downloadRagBundle")}
                  </a>
                  <p>{t("cheatsheets.ragBundleDescription")}</p>
                </div>
              )}
            </div>
            <div className="cheatsheet-catalog-grid">
              {CHEATSHEETS.filter((sheet) => sheet.category === group.id).map((sheet) => (
                <article key={sheet.slug} className="cheatsheet-catalog-card">
                  <div className="cheatsheet-card-topline">
                    <IconArticle className="h-5 w-5 text-primary" />
                    <span className="cheatsheet-page-count">{t("cheatsheets.pageCount", { count: sheet.pages })}</span>
                  </div>
                  <h3 className="font-display text-xl font-bold text-ink">{sheet.title}</h3>
                  <p className="cheatsheet-card-description">{sheet.description}</p>
                  <div className="cheatsheet-card-actions">
                    <Link to={`/cheatsheets/${sheet.slug}`} className="cheatsheet-action cheatsheet-action-primary">
                      {t("cheatsheets.open")} <span aria-hidden="true">→</span>
                      <span className="sr-only">: {sheet.title}</span>
                    </Link>
                    <a href={sheet.pdfUrl} download className="cheatsheet-action cheatsheet-action-secondary">
                      {t("cheatsheets.downloadPdf")}
                      <span className="sr-only">: {sheet.title}</span>
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
