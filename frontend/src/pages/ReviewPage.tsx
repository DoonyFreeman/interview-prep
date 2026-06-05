import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useReview } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Button } from "../components/Button";
import { ScorePill } from "../components/ScorePill";

export function ReviewPage() {
  const { t, i18n } = useTranslation();
  const review = useReview();

  if (review.isLoading) return <PageLoader label={t("common.loading")} />;
  if (review.isError || !review.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const { count, items } = review.data;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold text-ink">{t("review.title")}</h1>
      <p className="mt-1 mb-6 text-muted">{t("review.subtitle")}</p>

      {count === 0 ? (
        <div className="rounded-2xl border border-border bg-surface p-10 text-center shadow-sm">
          <div className="text-3xl">🎉</div>
          <p className="mt-3 font-semibold text-ink">{t("review.emptyTitle")}</p>
          <p className="mt-1 text-sm text-muted">{t("review.emptyHint")}</p>
          <Link to="/" className="mt-4 inline-block">
            <Button variant="secondary">{t("review.toCourses")}</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const due = new Date(item.due_at).toLocaleDateString(
              i18n.resolvedLanguage,
              { month: "short", day: "numeric" },
            );
            return (
              <div
                key={item.concept_slug}
                className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-4 shadow-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-semibold text-ink">
                      {item.concept_title}
                    </h3>
                    <ScorePill score={item.last_score} />
                  </div>
                  <div className="mt-1 text-xs text-faint">
                    {item.course_slug} · {item.lesson_slug} ·{" "}
                    {t("review.due", { date: due })}
                  </div>
                </div>
                {item.question_id != null && (
                  <Link
                    to={`/courses/${item.course_slug}/lessons/${item.lesson_slug}/quiz/${item.question_id}`}
                  >
                    <Button>{t("review.practice")}</Button>
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
