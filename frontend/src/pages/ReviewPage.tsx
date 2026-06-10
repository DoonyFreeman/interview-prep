import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useReview } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Button } from "../components/Button";
import { ScorePill } from "../components/ScorePill";
import { EmptyState } from "../components/EmptyState";
import { fadeInUp, staggerContainer } from "../lib/motion";

export function ReviewPage() {
  const { t, i18n } = useTranslation();
  const review = useReview();

  if (review.isLoading) return <PageLoader label={t("common.loading")} />;
  if (review.isError || !review.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const { count, items } = review.data;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-2xl font-bold text-ink">
        {t("review.title")}
      </h1>
      <p className="mt-1 mb-6 text-muted">{t("review.subtitle")}</p>

      {count === 0 ? (
        <EmptyState icon="🎉" title={t("review.emptyTitle")} hint={t("review.emptyHint")}>
          <Link to="/">
            <Button variant="secondary">{t("review.toCourses")}</Button>
          </Link>
        </EmptyState>
      ) : (
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="space-y-3"
        >
          {items.map((item) => {
            const due = new Date(item.due_at).toLocaleDateString(
              i18n.resolvedLanguage,
              { month: "short", day: "numeric" },
            );
            return (
              <motion.div
                key={item.concept_slug}
                variants={fadeInUp}
                className="flex items-center gap-4 rounded-2xl border border-border bg-surface p-4 shadow-card"
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
              </motion.div>
            );
          })}
        </motion.div>
      )}
    </div>
  );
}
