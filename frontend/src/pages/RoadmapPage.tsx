import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useProgress, useRoadmap } from "../api/hooks";
import type { RoadmapCourse, RoadmapExtraNode, RoadmapStage } from "../api/types";
import type { ProgressOverviewOut } from "../api/types";
import { courseAccent, courseInitials } from "../lib/accent";
import {
  courseCounts,
  lessonStatus,
  overallCounts,
  stageCounts,
  type LessonStatus,
} from "../lib/roadmap";
import { fadeInUp, staggerContainer } from "../lib/motion";
import { ProgressBar } from "../components/ProgressBar";
import { EmptyState } from "../components/EmptyState";
import { Skeleton, SkeletonCard } from "../components/Skeleton";
import { RoadmapDrawer, type RoadmapSelection } from "../components/RoadmapDrawer";
import { IconCheck, IconRoadmap } from "../components/icons";

/** One lesson chip: status dot/check + title, opens the drawer. */
function LessonChip({
  title,
  status,
  onClick,
}: {
  title: string;
  status: LessonStatus;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  const styles: Record<LessonStatus, string> = {
    done: "border-transparent bg-success-soft text-ink",
    attempted: "border-border bg-surface-2 text-ink",
    none: "border-border bg-surface text-muted hover:border-ink/20 hover:text-ink",
  };
  return (
    <button
      onClick={onClick}
      aria-label={`${title} — ${t(`roadmap.status.${status}`)}`}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors ${styles[status]}`}
    >
      {status === "done" ? (
        <IconCheck className="h-3.5 w-3.5 shrink-0 text-success" />
      ) : (
        <span
          aria-hidden
          className={`h-[7px] w-[7px] shrink-0 rounded-full ${
            status === "attempted" ? "bg-warn" : "border border-faint"
          }`}
        />
      )}
      {title}
    </button>
  );
}

function CourseCard({
  course,
  progress,
  onSelect,
}: {
  course: RoadmapCourse;
  progress: ProgressOverviewOut | undefined;
  onSelect: (sel: RoadmapSelection) => void;
}) {
  const accent = courseAccent(course.slug);
  const counts = courseCounts(progress, course);
  const complete = counts.done === counts.total && counts.total > 0;

  return (
    <motion.div variants={fadeInUp}>
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-card">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-display text-sm font-bold"
            style={{ background: accent.bg, color: accent.fg }}
          >
            {courseInitials(course.title)}
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-display text-[15px] font-bold text-ink">
              {course.title}
            </h3>
            <p className="mt-0.5 truncate text-xs text-muted">{course.summary}</p>
          </div>
          <div className="w-20 shrink-0 text-right">
            <span className="font-mono text-xs font-semibold text-muted">
              {counts.done}/{counts.total}
            </span>
            <ProgressBar
              value={counts.done}
              total={counts.total}
              tone={complete ? "celebrate" : "primary"}
              className="mt-1.5"
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {course.lessons.map((lesson) => {
            const status = lessonStatus(progress, course.slug, lesson.slug);
            return (
              <LessonChip
                key={lesson.slug}
                title={lesson.title}
                status={status}
                onClick={() => onSelect({ kind: "lesson", course, lesson, status })}
              />
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

function ExtraNodeCard({
  node,
  onSelect,
}: {
  node: RoadmapExtraNode;
  onSelect: (sel: RoadmapSelection) => void;
}) {
  const { t } = useTranslation();
  return (
    <motion.div variants={fadeInUp}>
      <div aria-hidden className="ml-[-1.875rem] h-4 w-px bg-border sm:ml-[-2.25rem]" />
      <button
        onClick={() => onSelect({ kind: "extra", node })}
        className="w-full rounded-2xl border border-dashed border-border bg-transparent p-5 text-left transition-colors hover:border-accent/50 hover:bg-surface"
      >
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent"
          >
            <IconRoadmap className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate font-display text-[15px] font-bold text-ink">
                {node.title}
              </h3>
              <span className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                {t("roadmap.externalTopic")}
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs text-muted">{node.summary}</p>
          </div>
        </div>
      </button>
    </motion.div>
  );
}

function StageSection({
  stage,
  index,
  progress,
  onSelect,
}: {
  stage: RoadmapStage;
  index: number;
  progress: ProgressOverviewOut | undefined;
  onSelect: (sel: RoadmapSelection) => void;
}) {
  const counts = stageCounts(progress, stage);
  const complete = counts.done === counts.total && counts.total > 0;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="relative pb-10"
    >
      {/* stage marker sits on the spine */}
      <div className="flex items-center gap-4">
        <span
          className={`z-10 -ml-14 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 font-display text-sm font-bold ${
            complete
              ? "border-success bg-success-soft text-success"
              : "border-border bg-surface text-ink"
          }`}
        >
          {complete ? <IconCheck className="h-4 w-4" /> : index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink">
            {stage.title}
          </h2>
          <p className="mt-0.5 text-sm text-muted">{stage.summary}</p>
        </div>
        <div className="hidden w-24 shrink-0 text-right sm:block">
          <span className="font-mono text-xs font-semibold text-muted">
            {counts.done}/{counts.total}
          </span>
          <ProgressBar
            value={counts.done}
            total={counts.total}
            tone={complete ? "celebrate" : "primary"}
            className="mt-1.5"
          />
        </div>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        className="mt-4 space-y-4"
      >
        {stage.courses.map((course) => (
          <CourseCard
            key={course.slug}
            course={course}
            progress={progress}
            onSelect={onSelect}
          />
        ))}
        {stage.extra_nodes.map((node) => (
          <ExtraNodeCard key={node.slug} node={node} onSelect={onSelect} />
        ))}
      </motion.div>
    </motion.section>
  );
}

export function RoadmapPage() {
  const { t } = useTranslation();
  const roadmap = useRoadmap();
  // Progress is an overlay: if it errors, the map still renders (all "none").
  const progress = useProgress();
  const [selection, setSelection] = useState<RoadmapSelection | null>(null);

  if (roadmap.isPending) {
    return (
      <div className="mx-auto max-w-3xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-3 h-4 w-72" />
        <div className="mt-8 space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }
  if (roadmap.isError) {
    return <EmptyState icon="🗺" title={t("common.error")} />;
  }

  const stages = roadmap.data.stages;
  const totals = overallCounts(progress.data, stages);
  const allDone = totals.done === totals.total && totals.total > 0;

  return (
    <div className="mx-auto max-w-3xl">
      <header>
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
          {t("roadmap.title")}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("roadmap.subtitle")}</p>
        <div className="mt-4 flex items-center gap-3">
          <ProgressBar
            value={totals.done}
            total={totals.total}
            tone={allDone ? "celebrate" : "primary"}
            className="max-w-xs"
          />
          <span className="shrink-0 text-xs font-semibold text-muted">
            {t("roadmap.lessonsOf", { done: totals.done, total: totals.total })}
          </span>
        </div>
      </header>

      {/* the spine */}
      <div className="relative mt-10 pl-14">
        <div
          aria-hidden
          className="absolute bottom-4 left-5 top-1 w-px bg-border"
        />
        {stages.map((stage, i) => (
          <StageSection
            key={stage.slug}
            stage={stage}
            index={i}
            progress={progress.data}
            onSelect={setSelection}
          />
        ))}
      </div>

      <RoadmapDrawer selection={selection} onClose={() => setSelection(null)} />
    </div>
  );
}
