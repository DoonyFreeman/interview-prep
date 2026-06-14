import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  useCourses,
  useProgress,
  useQuestionsProgress,
  useTestsOverview,
} from "../api/hooks";
import { Skeleton, SkeletonGrid } from "../components/Skeleton";
import { ProgressBar } from "../components/ProgressBar";
import { ScoreGauge } from "../components/ScoreGauge";
import { Button } from "../components/Button";
import { IconClipboardCheck } from "../components/icons";
import { useAuth } from "../auth/AuthContext";
import { courseAccent, courseInitials } from "../lib/accent";
import { courseProgressPct, overallProgressPct } from "../lib/progress";
import { fadeInUp, staggerContainer } from "../lib/motion";
import type {
  CourseProgressOut,
  CourseSummary,
  ProgressOverviewOut,
  QuestionsProgress,
  TestsCourseOverview,
  TestsOverview,
} from "../api/types";

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div title={hint} className={hint ? "cursor-help" : undefined}>
      <div className="font-display text-2xl font-bold text-ink">{value}</div>
      <div className="text-xs text-faint">
        {label}
        {hint && <span className="ml-0.5 text-faint">ⓘ</span>}
      </div>
    </div>
  );
}

function StatsHero({
  ov,
  questions,
  tests,
}: {
  ov: ProgressOverviewOut;
  questions?: QuestionsProgress;
  tests?: TestsOverview;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();

  // Overall progress that actually moves as you work (see lib/progress.ts):
  // reading a lesson or answering a concept earns a half, mastering it the full
  // point — so the ring isn't stuck at zero behind the strict mastery gate.
  const pct = overallProgressPct(ov);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="mb-3 flex flex-col items-center gap-5 rounded-2xl border border-border bg-surface p-6 shadow-raised sm:flex-row sm:gap-7"
    >
      <div title={t("dashboard.ringHint")} className="cursor-help">
        <ScoreGauge score={pct} size={104} />
      </div>
      <div className="flex-1 text-center sm:text-left">
        <h1 className="font-display text-xl font-bold tracking-tight text-ink">
          {t("dashboard.hello", { name: user?.display_name || "👋" })}
        </h1>
        <div className="mt-3 flex flex-wrap justify-center gap-6 sm:justify-start">
          <Stat
            label={t("dashboard.mastered")}
            value={`${ov.mastered_concepts}/${ov.total_concepts}`}
            hint={t("dashboard.masteredHint")}
          />
          <Stat
            label={t("dashboard.attempted")}
            value={`${ov.attempted_concepts}`}
            hint={t("dashboard.attemptedHint")}
          />
          <Stat
            label={t("dashboard.due")}
            value={`${ov.due_concepts}`}
            hint={t("dashboard.dueHint")}
          />
          {questions && (
            <Stat
              label={t("dashboard.answered")}
              value={`${questions.answered}/${questions.total}`}
              hint={t("dashboard.answeredHint")}
            />
          )}
          {tests && tests.total > 0 && (
            <Stat
              label={t("dashboard.tests")}
              value={`${tests.passed}/${tests.total}`}
              hint={t("dashboard.testsHint")}
            />
          )}
        </div>
      </div>
      <Link to="/review" className="w-full sm:w-auto">
        <Button
          variant={ov.due_concepts > 0 ? "primary" : "secondary"}
          className="w-full"
        >
          {ov.due_concepts > 0
            ? t("dashboard.reviewCta", { count: ov.due_concepts })
            : t("dashboard.reviewNone")}
        </Button>
      </Link>
    </motion.div>
  );
}

function CourseCard({
  course,
  p,
  tc,
}: {
  course: CourseSummary;
  p?: CourseProgressOut;
  tc?: TestsCourseOverview;
}) {
  const { t } = useTranslation();
  const accent = courseAccent(course.slug);
  const cpct = p ? courseProgressPct(p) : 0;
  const complete = cpct >= 100;

  return (
    <motion.div variants={fadeInUp} whileHover={{ y: -3 }} className="h-full">
      <Link
        to={`/courses/${course.slug}`}
        className="group flex h-full flex-col rounded-2xl border border-border bg-surface p-5 shadow-card transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-raised"
      >
        <div className="flex items-start gap-3">
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl font-display text-sm font-bold"
            style={{ background: accent.bg, color: accent.fg }}
          >
            {courseInitials(course.title)}
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="font-display font-bold leading-tight text-ink group-hover:text-primary">
              {course.title}
            </h2>
            <span className="text-xs font-semibold text-faint">
              {t("catalog.lessons", { count: course.lesson_count })}
            </span>
          </div>
        </div>
        <p className="mt-3 flex-1 text-sm leading-relaxed text-muted">
          {course.description}
        </p>
        {p && p.total_concepts > 0 && (
          <div className="mt-4">
            <div
              className="mb-1.5 flex justify-between text-xs text-faint"
              title={t("course.masteredOf", {
                mastered: p.mastered_concepts,
                total: p.total_concepts,
              })}
            >
              <span
                className={complete ? "font-semibold text-celebrate" : undefined}
              >
                {complete ? "✓ " : ""}
                {t("course.progress", { pct: cpct })}
              </span>
              {p.due_concepts > 0 && (
                <span className="font-semibold text-accent">● {p.due_concepts}</span>
              )}
            </div>
            <ProgressBar pct={cpct} tone={complete ? "celebrate" : "primary"} />
          </div>
        )}
        {tc && tc.total > 0 && (
          <div className="mt-2.5 flex items-center gap-1.5 text-xs text-faint">
            <IconClipboardCheck className="h-3.5 w-3.5 shrink-0" />
            <span
              className={
                tc.passed === tc.total ? "font-semibold text-celebrate" : undefined
              }
            >
              {t("catalog.testProgress", { passed: tc.passed, total: tc.total })}
            </span>
          </div>
        )}
      </Link>
    </motion.div>
  );
}

export function CatalogPage() {
  const { t } = useTranslation();
  const courses = useCourses();
  const progress = useProgress();
  const questions = useQuestionsProgress();
  const tests = useTestsOverview();

  if (courses.isLoading)
    return (
      <div>
        <div className="mb-8 flex flex-col items-center gap-5 rounded-2xl border border-border bg-surface p-6 shadow-card sm:flex-row">
          <Skeleton className="h-26 w-26 shrink-0 rounded-full" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-3 w-full max-w-md" />
          </div>
        </div>
        <SkeletonGrid count={6} />
      </div>
    );
  if (courses.isError || !courses.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const byCourse = new Map<string, CourseProgressOut>(
    (progress.data?.courses ?? []).map((c) => [c.slug, c]),
  );
  const testsByCourse = new Map<string, TestsCourseOverview>(
    (tests.data?.courses ?? []).map((c) => [c.slug, c]),
  );

  return (
    <div>
      {progress.data && (
        <StatsHero
          ov={progress.data}
          questions={questions.data}
          tests={tests.data}
        />
      )}
      <p className="mb-8 text-center text-xs text-faint sm:text-left">
        {t("dashboard.legend")}{" "}
        <Link
          to="/progress"
          className="font-semibold text-primary hover:underline"
        >
          {t("dashboard.seeProgress")}
        </Link>
      </p>

      <div className="mb-4">
        <h2 className="font-display text-lg font-bold text-ink">
          {t("catalog.title")}
        </h2>
        <p className="text-sm text-muted">{t("catalog.subtitle")}</p>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="grid gap-4 sm:grid-cols-2"
      >
        {courses.data.map((course) => (
          <CourseCard
            key={course.slug}
            course={course}
            p={byCourse.get(course.slug)}
            tc={testsByCourse.get(course.slug)}
          />
        ))}
      </motion.div>
    </div>
  );
}
