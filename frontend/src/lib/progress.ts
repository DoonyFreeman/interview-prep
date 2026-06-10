import type {
  CourseProgressOut,
  LessonProgressOut,
  ProgressOverviewOut,
} from "../api/types";

/**
 * "Live" progress that grows as you work, rather than only counting fully
 * mastered concepts. Each concept earns partial credit:
 *   - 0.5 for reading its lesson (marked done) or answering it at least once
 *   - 1.0 once it is mastered (SM-2: 2+ good reviews scoring ≥80)
 * A concept tops out at 1.0. This is what the dashboard ring and the course /
 * lesson progress bars all use, so they move on every action instead of
 * sitting near zero behind the strict mastery threshold.
 */
function lessonCredit(l: LessonProgressOut): { credit: number; total: number } {
  let credit = 0;
  for (const c of l.concepts) {
    if (c.mastered) credit += 1;
    else if (c.attempted || l.completed) credit += 0.5;
  }
  return { credit, total: l.concepts.length };
}

function pct(credit: number, total: number): number {
  return total > 0 ? Math.round((credit / total) * 100) : 0;
}

export function lessonProgressPct(l: LessonProgressOut): number {
  const { credit, total } = lessonCredit(l);
  return pct(credit, total);
}

export function courseProgressPct(c: CourseProgressOut): number {
  let credit = 0;
  let total = 0;
  for (const l of c.lessons) {
    const r = lessonCredit(l);
    credit += r.credit;
    total += r.total;
  }
  return pct(credit, total);
}

export function overallProgressPct(ov: ProgressOverviewOut): number {
  let credit = 0;
  let total = 0;
  for (const c of ov.courses) {
    for (const l of c.lessons) {
      const r = lessonCredit(l);
      credit += r.credit;
      total += r.total;
    }
  }
  return pct(credit, total);
}
