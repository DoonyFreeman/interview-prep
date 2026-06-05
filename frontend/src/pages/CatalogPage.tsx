import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCourses, useProgress } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { ProgressBar } from "../components/ProgressBar";
import type { CourseProgressOut } from "../api/types";

export function CatalogPage() {
  const { t } = useTranslation();
  const courses = useCourses();
  const progress = useProgress();

  if (courses.isLoading) return <PageLoader label={t("common.loading")} />;
  if (courses.isError || !courses.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const byCourse = new Map<string, CourseProgressOut>(
    (progress.data?.courses ?? []).map((c) => [c.slug, c]),
  );
  const ov = progress.data;

  return (
    <div>
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t("catalog.title")}</h1>
          <p className="mt-1 text-muted">{t("catalog.subtitle")}</p>
        </div>
        {ov && (
          <div className="flex gap-6">
            <Stat
              label={t("catalog.summaryMastered")}
              value={`${ov.mastered_concepts}/${ov.total_concepts}`}
            />
            <Stat label={t("catalog.summaryDue")} value={`${ov.due_concepts}`} />
          </div>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {courses.data.map((course) => {
          const p = byCourse.get(course.slug);
          return (
            <Link
              key={course.slug}
              to={`/courses/${course.slug}`}
              className="group flex flex-col rounded-2xl border border-border bg-surface p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-bold text-ink group-hover:text-primary">
                  {course.title}
                </h2>
                <span className="shrink-0 rounded-full bg-surface-2 px-2.5 py-1 text-xs font-semibold text-muted">
                  {t("catalog.lessons", { count: course.lesson_count })}
                </span>
              </div>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">
                {course.description}
              </p>
              {p && p.total_concepts > 0 && (
                <div className="mt-4">
                  <div className="mb-1.5 flex justify-between text-xs text-faint">
                    <span>
                      {t("course.masteredOf", {
                        mastered: p.mastered_concepts,
                        total: p.total_concepts,
                      })}
                    </span>
                    {p.due_concepts > 0 && (
                      <span className="font-semibold text-accent">
                        ● {p.due_concepts}
                      </span>
                    )}
                  </div>
                  <ProgressBar
                    value={p.mastered_concepts}
                    total={p.total_concepts}
                  />
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-right">
      <div className="text-2xl font-bold text-ink">{value}</div>
      <div className="text-xs text-faint">{label}</div>
    </div>
  );
}
