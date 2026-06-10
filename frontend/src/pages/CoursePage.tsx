import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useCourse, useProgress } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { ProgressBar } from "../components/ProgressBar";
import { courseAccent } from "../lib/accent";
import { lessonProgressPct } from "../lib/progress";
import { fadeInUp, staggerContainer } from "../lib/motion";
import type { LessonProgressOut } from "../api/types";

export function CoursePage() {
  const { t } = useTranslation();
  const { courseSlug = "" } = useParams();
  const course = useCourse(courseSlug);
  const progress = useProgress();

  if (course.isLoading) return <PageLoader label={t("common.loading")} />;
  if (course.isError || !course.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const accent = courseAccent(courseSlug);
  const courseProgress = progress.data?.courses.find(
    (c) => c.slug === courseSlug,
  );
  const byLesson = new Map<string, LessonProgressOut>(
    (courseProgress?.lessons ?? []).map((l) => [l.slug, l]),
  );

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/" className="text-sm font-medium text-muted transition-colors hover:text-ink">
        ← {t("course.back")}
      </Link>

      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight text-ink">
        {course.data.title}
      </h1>
      <p className="mt-2 text-muted">{course.data.description}</p>

      <h2 className="mb-3 mt-8 text-sm font-bold uppercase tracking-wide text-faint">
        {t("course.lessonsTitle")}
      </h2>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="space-y-3"
      >
        {course.data.lessons.map((lesson, idx) => {
          const p = byLesson.get(lesson.slug);
          return (
            <motion.div key={lesson.slug} variants={fadeInUp} whileHover={{ y: -2 }}>
              <Link
                to={`/courses/${courseSlug}/lessons/${lesson.slug}`}
                className="group flex items-center gap-4 rounded-2xl border border-border bg-surface p-4 shadow-card transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-raised"
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-display text-sm font-bold"
                  style={{ background: accent.bg, color: accent.fg }}
                >
                  {idx + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate font-display font-semibold text-ink group-hover:text-primary">
                      {lesson.title}
                    </h3>
                    {p?.completed && (
                      <span className="shrink-0 rounded-full bg-celebrate-soft px-2 py-0.5 text-[11px] font-semibold text-celebrate">
                        ✓ {t("course.completed")}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-faint">
                    <span>
                      {t("common.minutes", { count: lesson.duration_minutes })}
                    </span>
                    <span>·</span>
                    <span>
                      {t("course.concepts", { count: lesson.concept_count })}
                    </span>
                    {p && p.due_concepts > 0 && (
                      <span className="font-semibold text-accent">
                        ● {p.due_concepts}
                      </span>
                    )}
                  </div>
                  {p && p.total_concepts > 0 && (
                    <ProgressBar className="mt-2" pct={lessonProgressPct(p)} />
                  )}
                </div>
              </Link>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
