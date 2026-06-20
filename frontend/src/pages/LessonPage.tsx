import { useEffect, useRef } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, useScroll } from "motion/react";
import {
  useLesson,
  useLessonTestProgress,
  useMarkLesson,
  useProgress,
} from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Markdown } from "../components/Markdown";
import { Button } from "../components/Button";
import { IconMic, IconClipboardCheck } from "../components/icons";
import { useActiveAnchor } from "../lib/useActiveAnchor";

export function LessonPage() {
  const { t } = useTranslation();
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const location = useLocation();
  const lesson = useLesson(courseSlug, lessonSlug);
  const progress = useProgress();
  const testProgress = useLessonTestProgress(courseSlug, lessonSlug);
  const markLesson = useMarkLesson();

  const articleRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: articleRef,
    offset: ["start start", "end end"],
  });

  const anchors = (lesson.data?.concepts ?? []).map((c) => c.anchor);
  const activeAnchor = useActiveAnchor(anchors);

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
      {/* Reading-progress hairline, pinned just under the sticky header. */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed inset-x-0 top-15 z-30 h-0.5 origin-left bg-primary"
        aria-hidden
      />

      <article ref={articleRef} className="min-w-0 flex-1">
        <Link
          to={`/courses/${courseSlug}`}
          className="text-sm font-medium text-muted transition-colors hover:text-ink"
        >
          ← {t("lesson.backToCourse")}
        </Link>
        <div className="mt-2 mb-1 text-xs font-semibold uppercase tracking-wide text-faint">
          {t("common.minutes", { count: lesson.data.duration_minutes })}
        </div>

        {/* Mobile ToC — collapsed by default; the desktop sidebar handles lg+. */}
        {lesson.data.concepts.length > 0 && (
          <details className="mt-4 rounded-2xl border border-border bg-surface p-1 lg:hidden">
            <summary className="cursor-pointer list-none rounded-xl px-3 py-2 text-xs font-bold uppercase tracking-wide text-faint">
              {t("lesson.toc")} · {lesson.data.concepts.length}
            </summary>
            <ul className="space-y-0.5 px-1 pb-1">
              {lesson.data.concepts.map((c) => (
                <li key={c.slug}>
                  <a
                    href={`#${c.anchor}`}
                    className="block rounded-lg px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-ink"
                  >
                    {c.title}
                  </a>
                </li>
              ))}
            </ul>
          </details>
        )}

        <Markdown markdown={lesson.data.markdown} />
      </article>

      <aside className="mt-8 lg:mt-0 lg:w-64 lg:shrink-0">
        <div className="space-y-4 lg:sticky lg:top-24">
          {lesson.data.concepts.length > 0 && (
            <nav className="hidden rounded-2xl border border-border bg-surface p-4 lg:block">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-faint">
                {t("lesson.toc")}
              </h3>
              <ul className="space-y-0.5">
                {lesson.data.concepts.map((c) => {
                  const active = c.anchor === activeAnchor;
                  return (
                    <li key={c.slug}>
                      <a
                        href={`#${c.anchor}`}
                        className={`block rounded-lg border-l-2 px-2.5 py-1.5 text-sm transition-colors ${
                          active
                            ? "border-primary bg-primary-soft font-semibold text-primary"
                            : "border-transparent text-muted hover:bg-surface-2 hover:text-ink"
                        }`}
                      >
                        {c.title}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </nav>
          )}

          <div className="rounded-2xl border border-border bg-primary-soft p-4">
            <h3 className="font-display font-bold text-ink">
              {t("lesson.actionsTitle")}
            </h3>
            <p className="mt-1 text-sm text-muted">{t("lesson.actionsHint")}</p>
            <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}/quiz`}>
              <Button className="mt-3 w-full">
                <IconMic className="h-4 w-4" />
                {t("lesson.startQuiz")}
              </Button>
            </Link>
            {(testProgress.data?.total ?? 0) > 0 && (
              <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}/test`}>
                <Button variant="secondary" className="mt-2 w-full">
                  <IconClipboardCheck className="h-4 w-4" />
                  {t("lesson.startTest")}
                  {testProgress.data && testProgress.data.attempts > 0 && (
                    <span
                      className={`ml-1.5 font-bold ${
                        testProgress.data.passed ? "text-celebrate" : "text-muted"
                      }`}
                    >
                      {testProgress.data.best_score}%
                    </span>
                  )}
                </Button>
              </Link>
            )}
            <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}/questions`}>
              <Button variant="ghost" className="mt-2 w-full">
                {t("lesson.allQuestions")}
              </Button>
            </Link>
            {completed ? (
              <p className="mt-3 text-center text-sm font-semibold text-celebrate">
                ✓ {t("lesson.marked")}
              </p>
            ) : (
              <Button
                variant="secondary"
                className="mt-2 w-full"
                loading={markLesson.isPending}
                onClick={() =>
                  markLesson.mutate({ courseSlug, lessonSlug, completed: true })
                }
              >
                {t("lesson.markDone")}
              </Button>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
