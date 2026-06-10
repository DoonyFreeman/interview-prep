import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLessonQuestions } from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Button } from "../components/Button";
import { ScorePill } from "../components/ScorePill";
import { AttemptHistory } from "../components/AttemptHistory";
import type { QuestionStatus } from "../api/types";

function StatusLabel({ q }: { q: QuestionStatus }) {
  const { t } = useTranslation();
  if (q.attempts === 0) {
    return <span className="text-xs text-faint">{t("questions.notAttempted")}</span>;
  }
  return (
    <span className="text-xs text-muted">
      {q.attempts === 1
        ? t("questions.attemptsOne")
        : t("questions.attemptsMany", { count: q.attempts })}
    </span>
  );
}

export function QuestionsPage() {
  const { t } = useTranslation();
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const data = useLessonQuestions(courseSlug, lessonSlug);
  const [openId, setOpenId] = useState<number | null>(null);

  if (data.isLoading) return <PageLoader label={t("common.loading")} />;
  if (data.isError || !data.data)
    return <p className="text-danger">{t("common.error")}</p>;

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to={`/courses/${courseSlug}/lessons/${lessonSlug}`}
        className="text-sm font-medium text-muted hover:text-ink"
      >
        ← {t("questions.backToLesson")}
      </Link>

      <h1 className="mt-3 font-display text-2xl font-bold tracking-tight text-ink">
        {t("questions.title")}
      </h1>
      <p className="mt-1 mb-6 text-muted">{t("questions.subtitle")}</p>

      <div className="space-y-3">
        {data.data.questions.map((q) => (
          <div
            key={q.id}
            className="rounded-2xl border border-border bg-surface p-4 shadow-card"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-semibold text-primary">
                {q.concept_title}
              </span>
              {q.last_score != null && <ScorePill score={q.last_score} />}
              <span className="ml-auto">
                <StatusLabel q={q} />
              </span>
            </div>
            <p className="text-sm leading-relaxed text-ink">{q.text}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Link
                to={`/courses/${courseSlug}/lessons/${lessonSlug}/quiz/${q.id}`}
              >
                <Button variant={q.attempts === 0 ? "primary" : "secondary"}>
                  {q.attempts === 0
                    ? t("questions.practice")
                    : t("questions.retry")}
                </Button>
              </Link>
              {q.attempts > 0 && (
                <button
                  onClick={() => setOpenId(openId === q.id ? null : q.id)}
                  className="rounded-lg px-3 py-1.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  {openId === q.id
                    ? t("questions.hideAnswers")
                    : t("questions.myAnswers", { count: q.attempts })}
                </button>
              )}
            </div>
            {openId === q.id && <AttemptHistory questionId={q.id} />}
          </div>
        ))}
      </div>
    </div>
  );
}
