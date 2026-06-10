import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useQuestionsProgress } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { ProgressBar } from "../components/ProgressBar";
import { fadeInUp, staggerContainer } from "../lib/motion";
import type { CourseQuestionsProgress } from "../api/types";

function CourseBlock({ c }: { c: CourseQuestionsProgress }) {
  const { t } = useTranslation();
  const done = c.total > 0 && c.answered >= c.total;
  return (
    <motion.div
      variants={fadeInUp}
      className="rounded-2xl border border-border bg-surface p-5 shadow-card"
    >
      <div className="mb-1 flex items-center justify-between gap-3">
        <Link
          to={`/courses/${c.slug}`}
          className="font-display font-bold text-ink hover:text-primary"
        >
          {c.title}
        </Link>
        <span className="shrink-0 text-sm font-semibold text-muted">
          {done && <span className="mr-1 text-celebrate">✓</span>}
          {c.answered}/{c.total}
        </span>
      </div>
      <ProgressBar
        value={c.answered}
        total={c.total}
        tone={done ? "celebrate" : "primary"}
        className="mb-3"
      />

      <ul className="divide-y divide-border">
        {c.lessons.map((l) => {
          const left = l.total - l.answered;
          const lessonDone = l.total > 0 && l.answered >= l.total;
          return (
            <li
              key={l.slug}
              className="flex items-center justify-between gap-3 py-2"
            >
              <Link
                to={`/courses/${c.slug}/lessons/${l.slug}/questions`}
                className={`min-w-0 flex-1 truncate text-sm hover:text-primary ${
                  lessonDone ? "text-faint" : "text-ink"
                }`}
              >
                {lessonDone && <span className="mr-1 text-celebrate">✓</span>}
                {l.title}
              </Link>
              <span className="shrink-0 text-xs font-medium text-faint">
                {left > 0 ? (
                  <span className="text-accent">
                    {t("progress.left", { count: left })}
                  </span>
                ) : (
                  <span className="text-celebrate">{t("progress.allDone")}</span>
                )}
                <span className="ml-2 text-muted">
                  {l.answered}/{l.total}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </motion.div>
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
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-2xl font-bold text-ink">
        {t("progress.title")}
      </h1>
      <p className="mt-1 text-muted">{t("progress.subtitle")}</p>

      <div className="mt-5 mb-6 rounded-2xl border border-border bg-surface p-5 shadow-raised">
        <div className="mb-1 flex items-end justify-between">
          <span className="text-sm font-semibold text-ink">
            {t("progress.answeredOf", { answered, total })}
          </span>
          <span className="font-display text-2xl font-bold text-primary">
            {pct}%
          </span>
        </div>
        <ProgressBar value={answered} total={total} />
        {left > 0 && (
          <p className="mt-2 text-xs font-semibold text-accent">
            {t("progress.left", { count: left })}
          </p>
        )}
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="space-y-4"
      >
        {courses
          .filter((c) => c.total > 0)
          .map((c) => (
            <CourseBlock key={c.slug} c={c} />
          ))}
      </motion.div>
    </div>
  );
}
