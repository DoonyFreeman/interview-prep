import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuestionsProgress } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { ProgressBar } from "../components/ProgressBar";
import type { CourseQuestionsProgress } from "../api/types";

function CourseBlock({ c }: { c: CourseQuestionsProgress }) {
  const { t } = useTranslation();
  const done = c.total > 0 && c.answered >= c.total;
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="mb-1 flex items-center justify-between gap-3">
        <Link
          to={`/courses/${c.slug}`}
          className="font-bold text-ink hover:text-primary"
        >
          {c.title}
        </Link>
        <span className="shrink-0 text-sm font-semibold text-muted">
          {done && <span className="mr-1 text-success">✓</span>}
          {c.answered}/{c.total}
        </span>
      </div>
      <ProgressBar value={c.answered} total={c.total} className="mb-3" />

      <ul className="divide-y divide-border">
        {c.lessons.map((l) => {
          const left = l.total - l.answered;
          return (
            <li
              key={l.slug}
              className="flex items-center justify-between gap-3 py-2"
            >
              <Link
                to={`/courses/${c.slug}/lessons/${l.slug}/questions`}
                className="min-w-0 flex-1 truncate text-sm text-ink hover:text-primary"
              >
                {l.title}
              </Link>
              <span className="shrink-0 text-xs font-medium text-faint">
                {left > 0 ? (
                  <span className="text-accent">
                    {t("progress.left", { count: left })}
                  </span>
                ) : (
                  <span className="text-success">{t("progress.allDone")}</span>
                )}
                <span className="ml-2 text-muted">
                  {l.answered}/{l.total}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ProgressPage() {
  const { t } = useTranslation();
  const q = useQuestionsProgress();

  if (q.isLoading) return <PageLoader label={t("common.loading")} />;
  if (q.isError || !q.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const { total, answered, courses } = q.data;
  const left = total - answered;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold text-ink">{t("progress.title")}</h1>
      <p className="mt-1 text-muted">{t("progress.subtitle")}</p>

      <div className="mt-5 mb-6 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-semibold text-ink">
            {t("progress.answeredOf", { answered, total })}
          </span>
          <span className="text-sm font-semibold text-accent">
            {t("progress.left", { count: left })}
          </span>
        </div>
        <ProgressBar value={answered} total={total} />
      </div>

      <div className="space-y-4">
        {courses
          .filter((c) => c.total > 0)
          .map((c) => (
            <CourseBlock key={c.slug} c={c} />
          ))}
      </div>
    </div>
  );
}
