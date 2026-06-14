import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import {
  useEvaluate,
  useHint,
  useNextQuestion,
  useQuestion,
} from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Button } from "../components/Button";
import { EvaluationCard } from "../components/EvaluationCard";
import { EmptyState } from "../components/EmptyState";
import { IconRefresh } from "../components/icons";
import { apiErrorMessage } from "../lib/api";
import type { EvaluationOut } from "../api/types";

/** Difficulty 1–5 rendered as filled dots — gentler than "3/5". */
function Difficulty({ level }: { level: number }) {
  const { t } = useTranslation();
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-muted"
      title={`${t("quiz.difficulty")}: ${level}/5`}
    >
      {t("quiz.difficulty")}
      <span className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            className={`h-1.5 w-1.5 rounded-full ${
              i <= level ? "bg-accent" : "bg-border"
            }`}
          />
        ))}
      </span>
    </span>
  );
}

export function QuizPage() {
  const { t } = useTranslation();
  const { courseSlug = "", lessonSlug = "", questionId } = useParams();

  // Two modes: practice one specific question (questionId in the URL), or pull
  // a fresh due-aware question from the lesson ("next").
  const single = questionId != null;
  const qId = single ? Number(questionId) : null;
  const oneQuery = useQuestion(qId);
  const nextQuery = useNextQuestion(courseSlug, lessonSlug, { enabled: !single });
  const source = single ? oneQuery : nextQuery;
  const question = source.data;

  const evaluate = useEvaluate();
  const hint = useHint();

  const [answer, setAnswer] = useState("");
  const [hintUsed, setHintUsed] = useState(false);
  const [hintText, setHintText] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluationOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  function resetAttempt() {
    setAnswer("");
    setHintUsed(false);
    setHintText(null);
    setResult(null);
    setError(null);
  }

  async function check() {
    if (!question) return;
    if (!answer.trim()) {
      setError(t("quiz.emptyAnswer"));
      return;
    }
    setError(null);
    try {
      const data = await evaluate.mutateAsync({
        questionId: question.id,
        answerText: answer,
        hintUsed,
      });
      setResult(data);
    } catch (err) {
      setError(apiErrorMessage(err, t("common.error")));
    }
  }

  async function askHint() {
    if (!question) return;
    try {
      const data = await hint.mutateAsync({
        questionId: question.id,
        answerText: answer,
      });
      setHintText(data.hint);
      setHintUsed(true);
    } catch (err) {
      setError(apiErrorMessage(err, t("common.error")));
    }
  }

  function nextQuestion() {
    resetAttempt();
    nextQuery.refetch();
  }

  // Ctrl/Cmd+Enter submits — keyboard-friendly for a text-heavy flow.
  function onKeyDown(e: React.KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      check();
    }
  }

  if (source.isLoading) return <PageLoader label={t("common.loading")} />;
  if (source.isError || !question)
    return (
      <div className="mx-auto max-w-2xl">
        <EmptyState icon="🎯" title={t("quiz.noQuestions")}>
          <Link to={`/courses/${courseSlug}/lessons/${lessonSlug}`}>
            <Button variant="secondary">{t("lesson.backToCourse")}</Button>
          </Link>
        </EmptyState>
      </div>
    );

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to={
          single
            ? `/courses/${courseSlug}/lessons/${lessonSlug}/questions`
            : `/courses/${courseSlug}/lessons/${lessonSlug}`
        }
        className="inline-flex items-center gap-1 text-sm font-medium text-muted transition-colors hover:text-ink"
      >
        ← {single ? t("quiz.toQuestions") : t("lesson.backToCourse")}
      </Link>

      {/* Question */}
      <div className="mt-3 rounded-2xl border border-border bg-surface p-5 shadow-card sm:p-6">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary">
            {question.concept_title}
          </span>
          <Difficulty level={question.difficulty} />
        </div>
        <p className="text-lg font-semibold leading-relaxed text-ink">
          {question.text}
        </p>
      </div>

      {/* Answer or result — crossfade between the two phases. */}
      <AnimatePresence mode="wait" initial={false}>
        {!result ? (
          <motion.div
            key="input"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="mt-4"
          >
            <label className="mb-1.5 block text-xs font-semibold text-muted">
              {t("quiz.answerLabel")}
            </label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={t("quiz.answerPlaceholder")}
              rows={6}
              autoFocus
              className="w-full resize-y rounded-2xl border border-border bg-surface p-4 text-sm leading-relaxed outline-none transition-colors focus:border-primary"
            />

            <AnimatePresence>
              {hintText && (
                <motion.div
                  initial={{ opacity: 0, height: 0, marginTop: 0 }}
                  animate={{ opacity: 1, height: "auto", marginTop: 12 }}
                  exit={{ opacity: 0, height: 0, marginTop: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="rounded-xl border border-accent/30 bg-accent-soft px-4 py-3 text-sm text-ink">
                    <span className="font-semibold text-accent">
                      💡 {t("quiz.hint")}:{" "}
                    </span>
                    {hintText}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {error && (
              <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <div className="mt-4 flex items-center justify-between gap-3">
              <Button variant="ghost" onClick={askHint} loading={hint.isPending}>
                {!hint.isPending && "💡"}
                {hint.isPending ? t("quiz.hintLoading") : t("quiz.hint")}
              </Button>
              <Button onClick={check} loading={evaluate.isPending}>
                {evaluate.isPending ? t("quiz.checking") : t("quiz.check")}
              </Button>
            </div>
            <p className="mt-2 text-right text-[11px] text-faint">⌘/Ctrl + Enter</p>
          </motion.div>
        ) : (
          <motion.div
            key="result"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="mt-4 space-y-4"
          >
            <div className="rounded-2xl border border-border bg-surface-2 p-4 text-sm text-muted">
              <span className="font-semibold text-faint">
                {t("quiz.answerLabel")}:{" "}
              </span>
              {answer}
            </div>

            <EvaluationCard data={result} />

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Link
                to={`/courses/${question.course_slug}/lessons/${question.lesson_slug}#${question.anchor}`}
              >
                <Button variant="ghost">← {t("quiz.backToTheory")}</Button>
              </Link>
              {single ? (
                <div className="flex gap-2">
                  <Link
                    to={`/courses/${courseSlug}/lessons/${lessonSlug}/questions`}
                  >
                    <Button variant="secondary">{t("quiz.toQuestions")}</Button>
                  </Link>
                  <Button onClick={resetAttempt}>
                    <IconRefresh className="h-4 w-4" />
                    {t("quiz.again")}
                  </Button>
                </div>
              ) : (
                <Button onClick={nextQuestion} loading={nextQuery.isFetching}>
                  {t("quiz.next")} →
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
