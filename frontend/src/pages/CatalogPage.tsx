import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCourses, useProgress } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { ProgressBar } from "../components/ProgressBar";
import { ScoreGauge } from "../components/ScoreGauge";
import { Button } from "../components/Button";
import { useAuth } from "../auth/AuthContext";
import type { CourseProgressOut, ProgressOverviewOut } from "../api/types";

function StatsHero({ ov }: { ov: ProgressOverviewOut }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const pct =
    ov.total_concepts > 0
      ? Math.round((ov.mastered_concepts / ov.total_concepts) * 100)
      : 0;

  return (
    <div className="mb-8 flex flex-col items-center gap-5 rounded-2xl border border-border bg-surface p-6 shadow-sm sm:flex-row sm:gap-7">
      <ScoreGauge score={pct} size={104} />
      <div className="flex-1 text-center sm:text-left">
        <h1 className="text-xl font-bold text-ink">
          {t("dashboard.hello", { name: user?.display_name || "👋" })}
        </h1>
        <div className="mt-3 flex justify-center gap-6 sm:justify-start">
          <Stat label={t("dashboard.mastered")} value={`${ov.mastered_concepts}/${ov.total_concepts}`} />
          <Stat label={t("dashboard.attempted")} value={`${ov.attempted_concepts}`} />
          <Stat label={t("dashboard.due")} value={`${ov.due_concepts}`} />
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
    </div>
  );
}

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

  return (
    <div>
      {progress.data && <StatsHero ov={progress.data} />}

      <div className="mb-4">
        <h2 className="text-lg font-bold text-ink">{t("catalog.title")}</h2>
        <p className="text-sm text-muted">{t("catalog.subtitle")}</p>
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
    <div>
      <div className="text-2xl font-bold text-ink">{value}</div>
      <div className="text-xs text-faint">{label}</div>
    </div>
  );
}
