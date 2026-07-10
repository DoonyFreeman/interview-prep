import type {
  ProgressOverviewOut,
  RoadmapCourse,
  RoadmapResource,
  RoadmapStage,
} from "../api/types";

/**
 * Pure helpers for the roadmap page: merge the static roadmap (stages →
 * courses → lessons) with the user's progress overview, and resolve which
 * resources a lesson drawer should show (own list or course fallback).
 */

export type LessonStatus = "done" | "attempted" | "none";

export function lessonStatus(
  progress: ProgressOverviewOut | undefined,
  courseSlug: string,
  lessonSlug: string,
): LessonStatus {
  const lesson = progress?.courses
    .find((c) => c.slug === courseSlug)
    ?.lessons.find((l) => l.slug === lessonSlug);
  if (!lesson) return "none";
  if (lesson.completed) return "done";
  return lesson.attempted_concepts > 0 ? "attempted" : "none";
}

export interface Counts {
  done: number;
  total: number;
}

/** Totals come from the roadmap (source of truth for what exists), progress
 *  only marks completion — so a progress payload lagging behind new content
 *  can't inflate percentages. */
export function courseCounts(
  progress: ProgressOverviewOut | undefined,
  course: RoadmapCourse,
): Counts {
  const done = course.lessons.filter(
    (l) => lessonStatus(progress, course.slug, l.slug) === "done",
  ).length;
  return { done, total: course.lessons.length };
}

export function stageCounts(
  progress: ProgressOverviewOut | undefined,
  stage: RoadmapStage,
): Counts {
  return stage.courses.reduce<Counts>(
    (acc, course) => {
      const c = courseCounts(progress, course);
      return { done: acc.done + c.done, total: acc.total + c.total };
    },
    { done: 0, total: 0 },
  );
}

export function overallCounts(
  progress: ProgressOverviewOut | undefined,
  stages: RoadmapStage[],
): Counts {
  return stages.reduce<Counts>(
    (acc, stage) => {
      const s = stageCounts(progress, stage);
      return { done: acc.done + s.done, total: acc.total + s.total };
    },
    { done: 0, total: 0 },
  );
}

const TYPE_ORDER: Record<string, number> = { video: 0, article: 1, docs: 2 };

export function sortResources(resources: RoadmapResource[]): RoadmapResource[] {
  return [...resources].sort(
    (a, b) => (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9),
  );
}

/** A lesson's drawer resources: its own curated list, else the course's
 *  shared list (flagged so the UI can caption the fallback). */
export function resourcesFor(
  course: RoadmapCourse,
  lessonSlug: string,
): { resources: RoadmapResource[]; fromCourse: boolean } {
  const own =
    course.lessons.find((l) => l.slug === lessonSlug)?.resources ?? [];
  if (own.length > 0) return { resources: sortResources(own), fromCourse: false };
  return { resources: sortResources(course.resources), fromCourse: true };
}
