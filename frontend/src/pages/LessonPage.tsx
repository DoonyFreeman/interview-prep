import { useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLesson, useMarkLesson, useProgress } from "../api/hooks";
import { PageLoader, Spinner } from "../components/Spinner";
import { Markdown } from "../components/Markdown";
import { Button } from "../components/Button";

export function LessonPage() {
  const { t } = useTranslation();
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const location = useLocation();
  const lesson = useLesson(courseSlug, lessonSlug);
  const progress = useProgress();
  const markLesson = useMarkLesson();

  // Once the markdown is rendered, jump to the #anchor from "Back to theory".
  useEffect(() => {
    if (!lesson.data || !location.hash) return;
    const id = decodeURIComponent(location.hash.slice(1));
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [lesson.data, location.hash]);

  if (lesson.isLoading) return <PageLoader label={t("common.loading")} />;
  if (lesson.isError || !lesson.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const completed =
    progress.data?.courses
      .find((c) => c.slug === courseSlug)
      ?.lessons.find((l) => l.slug === lessonSlug)?.completed ?? false;

  return (
    <div className="lg:flex lg:gap-10">
      <article className="min-w-0 flex-1">
        <Link
          to={`/courses/${courseSlug}`}
          className="text-sm font-medium text-muted hover:text-ink"
        >
          ← {t("lesson.backToCourse")}
        </Link>
        <div className="mt-2 mb-1 text-xs font-semibold uppercase tracking-wide text-faint">
          {t("common.minutes", { count: lesson.data.duration_minutes })}
        </div>
        <Markdown markdown={lesson.data.markdown} />
      </article>

      <aside className="mt-8 lg:mt-0 lg:w-64 lg:shrink-0">
        <div className="lg:sticky lg:top-24 space-y-4">
          {lesson.data.concepts.length > 0 && (
            <nav className="rounded-2xl border border-border bg-surface p-4">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-faint">
                {t("lesson.toc")}
              </h3>
              <ul className="space-y-1">
                {lesson.data.concepts.map((c) => (
                  <li key={c.slug}>
                    <a
                      href={`#${c.anchor}`}
                      className="block rounded-lg px-2 py-1.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-ink"
                    >
                      {c.title}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          )}

          <div className="rounded-2xl border border-border bg-primary-soft p-4">
            <h3 className="font-bold text-ink">{t("lesson.actionsTitle")}</h3>
            <p className="mt-1 text-sm text-muted">{t("lesson.actionsHint")}</p>
            <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}/quiz`}>
              <Button className="mt-3 w-full">{t("lesson.startQuiz")}</Button>
            </Link>
            <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}/questions`}>
              <Button variant="ghost" className="mt-2 w-full">
                {t("lesson.allQuestions")}
              </Button>
            </Link>
            {completed ? (
              <p className="mt-3 text-center text-sm font-semibold text-success">
                ✓ {t("lesson.marked")}
              </p>
            ) : (
              <Button
                variant="secondary"
                className="mt-2 w-full"
                disabled={markLesson.isPending}
                onClick={() =>
                  markLesson.mutate({ courseSlug, lessonSlug, completed: true })
                }
              >
                {markLesson.isPending && <Spinner />}
                {t("lesson.markDone")}
              </Button>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
