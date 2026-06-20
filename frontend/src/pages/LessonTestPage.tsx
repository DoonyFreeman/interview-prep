import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  useLessonTest,
  useLessonTestProgress,
  useRecordLessonTest,
} from "../api/hooks";
import { PageLoader, Spinner } from "../components/Spinner";
import { Button } from "../components/Button";
import { Markdown } from "../components/Markdown";
import { ScoreGauge } from "../components/ScoreGauge";
import { EmptyState } from "../components/EmptyState";
import { CelebrateBurst } from "../components/CelebrateBurst";
import { IconClipboardCheck, IconRefresh } from "../components/icons";
import { fade } from "../lib/motion";
import {
  prepareTest,
  scorePct,
  toResultItems,
  type Answer,
  type PreparedMcq,
} from "../lib/lessonTest";

type Phase = "intro" | "run" | "result";

export function LessonTestPage() {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const test = useLessonTest(courseSlug, lessonSlug);
  const priorProgress = useLessonTestProgress(courseSlug, lessonSlug);
  const record = useRecordLessonTest(courseSlug, lessonSlug);

  const lessonPath = `/courses/${courseSlug}/lessons/${lessonSlug}`;

  const [phase, setPhase] = useState<Phase>("intro");
  const [prepared, setPrepared] = useState<PreparedMcq[]>([]);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [picked, setPicked] = useState<number | null>(null);
  const recorded = useRef(false);

  function start(onlySlugs?: string[]) {
    const all = test.data?.questions ?? [];
    const q = prepareTest(all, onlySlugs ? { onlySlugs } : {});
    if (q.length === 0) return;
    recorded.current = false;
    setPrepared(q);
    setIndex(0);
    setAnswers({});
    setPicked(null);
    setPhase("run");
  }

  function choose(optIndex: number) {
    if (picked != null) return;
    const q = prepared[index];
    const opt = q.options[optIndex];
    if (!opt) return;
    setPicked(optIndex);
    setAnswers((a) => ({
      ...a,
      [q.slug]: {
        slug: q.slug,
        conceptTitle: q.conceptTitle,
        anchor: q.anchor,
        text: q.text,
        correct: opt.correct,
        pickedLabel: opt.label,
        correctLabel: q.options.find((o) => o.correct)?.label,
        explanationMd: q.explanationMd,
      },
    }));
  }

  function next() {
    if (index + 1 >= prepared.length) setPhase("result");
    else {
      setIndex((i) => i + 1);
      setPicked(null);
    }
  }

  // Keyboard: 1–N to pick an option, Enter/Space to advance after the reveal.
  useEffect(() => {
    if (phase !== "run") return;
    const onKey = (e: KeyboardEvent) => {
      const q = prepared[index];
      if (!q) return;
      if (picked == null) {
        const n = Number(e.key);
        if (n >= 1 && n <= q.options.length) {
          e.preventDefault();
          choose(n - 1);
        }
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, index, picked, prepared]);

  // Persist the result once when entering the result phase.
  useEffect(() => {
    if (phase !== "result" || recorded.current) return;
    recorded.current = true;
    const items = toResultItems(Object.values(answers));
    if (items.length) record.mutate(items);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  if (test.isLoading) return <PageLoader label={t("common.loading")} />;
  if (test.isError || !test.data)
    return <p className="text-danger">{t("common.error")}</p>;

  const totalQ = test.data.questions.length;

  // ----------------------------------------------------------- empty bank ---
  if (totalQ === 0) {
    return (
      <div className="mx-auto max-w-2xl">
        <Link to={lessonPath} className="text-sm font-medium text-muted hover:text-ink">
          ← {t("lessonTest.toLesson")}
        </Link>
        <div className="mt-6">
          <EmptyState
            icon={<IconClipboardCheck className="h-7 w-7 text-faint" />}
            title={t("lessonTest.empty")}
          />
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- intro ---
  if (phase === "intro") {
    const prior = priorProgress.data;
    const hasPrior = (prior?.answered ?? 0) > 0;
    return (
      <div className="mx-auto max-w-lg">
        <Link to={lessonPath} className="text-sm font-medium text-muted hover:text-ink">
          ← {t("lessonTest.toLesson")}
        </Link>
        <motion.div
          variants={fade}
          initial="hidden"
          animate="show"
          className="mt-4 rounded-2xl border border-border bg-surface p-6 text-center shadow-card"
        >
          <div className="flex justify-center text-primary" aria-hidden>
            <IconClipboardCheck className="h-10 w-10" />
          </div>
          <h1 className="mt-3 font-display text-2xl font-bold tracking-tight text-ink">
            {t("lessonTest.title")}
          </h1>
          <p className="mt-1 text-sm font-medium text-muted">
            {t("lessonTest.introMeta", { count: totalQ })}
          </p>
          <p className="mx-auto mt-3 max-w-sm text-sm text-faint">
            {t("lessonTest.introNote")}
          </p>

          {hasPrior && (
            <div className="mx-auto mt-5 inline-flex items-center gap-2 rounded-full bg-primary-soft px-4 py-1.5 text-sm font-semibold text-primary">
              {t("lessonTest.lastResult")}
              <span className="text-celebrate">
                {prior!.correct}/{prior!.total}
              </span>
            </div>
          )}

          <div className="mt-6">
            <Button onClick={() => start()} className="w-full sm:w-auto sm:px-10">
              {t("lessonTest.start")} →
            </Button>
          </div>
        </motion.div>
      </div>
    );
  }

  // ------------------------------------------------------------------ run ---
  if (phase === "run") {
    const q = prepared[index];
    if (!q) return <PageLoader label={t("common.loading")} />;
    const correctSoFar = Object.values(answers).filter((a) => a.correct).length;
    const fraction = (index + (picked != null ? 1 : 0)) / prepared.length;

    return (
      <div className="mx-auto max-w-2xl">
        {/* Progress bar + counter + live tally */}
        <div className="mb-4">
          <div className="mb-1.5 flex items-center justify-between text-xs font-semibold text-faint">
            <span>
              {t("lessonTest.progress", {
                current: index + 1,
                total: prepared.length,
              })}
            </span>
            <span className="flex items-center gap-3">
              <span className="text-success">
                {t("lessonTest.tally", { count: correctSoFar })}
              </span>
              <Link to={lessonPath} className="text-muted hover:text-ink" aria-label="close">
                ✕
              </Link>
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <motion.div
              className="h-full rounded-full bg-primary"
              animate={{ width: `${fraction * 100}%` }}
              transition={reduce ? { duration: 0 } : { duration: 0.3 }}
            />
          </div>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={index}
            variants={reduce ? undefined : fade}
            initial="hidden"
            animate="show"
            exit="exit"
          >
            <div className="rounded-2xl border border-border bg-surface p-5 shadow-card">
              <div className="text-[11px] font-bold uppercase tracking-wide text-faint">
                {q.conceptTitle}
              </div>
              <div className="prose-sm mt-1">
                <Markdown markdown={q.text} />
              </div>
            </div>

            <div className="mt-4 space-y-2">
              {q.options.map((o, i) => {
                const isPicked = picked === i;
                const reveal = picked != null;
                let cls = "border-border bg-surface hover:bg-surface-2 text-ink";
                let badge = "border-border bg-surface-2 text-muted";
                if (reveal && o.correct) {
                  cls = "border-success/50 bg-success-soft text-success";
                  badge = "border-success/40 bg-success text-white";
                } else if (reveal && isPicked) {
                  cls = "border-danger/50 bg-danger-soft text-danger";
                  badge = "border-danger/40 bg-danger text-white";
                } else if (reveal) {
                  cls = "border-border bg-surface text-faint";
                }
                return (
                  <button
                    key={i}
                    onClick={() => choose(i)}
                    disabled={reveal}
                    className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm font-medium transition-colors disabled:cursor-default ${cls}`}
                  >
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-xs font-bold ${badge}`}
                    >
                      {reveal && o.correct ? "✓" : reveal && isPicked ? "✗" : i + 1}
                    </span>
                    <span>{o.label}</span>
                  </button>
                );
              })}
            </div>

            {picked != null && (
              <motion.div
                variants={reduce ? undefined : fade}
                initial="hidden"
                animate="show"
                className="mt-4 rounded-2xl border border-border bg-surface-2 p-4"
              >
                <div
                  className={`text-sm font-bold ${
                    answers[q.slug]?.correct ? "text-success" : "text-danger"
                  }`}
                >
                  {answers[q.slug]?.correct
                    ? `✓ ${t("lessonTest.verdictCorrect")}`
                    : `✗ ${t("lessonTest.verdictWrong")}`}
                </div>
                {q.explanationMd && (
                  <div className="prose-sm mt-1.5">
                    <Markdown markdown={q.explanationMd} />
                  </div>
                )}
                <div className="mt-3 flex items-center justify-between gap-3">
                  <Link
                    to={`${lessonPath}#${q.anchor}`}
                    className="text-xs font-semibold text-primary hover:underline"
                  >
                    {t("lessonTest.toTheory")} →
                  </Link>
                  <Button onClick={next} autoFocus>
                    {index + 1 >= prepared.length
                      ? t("lessonTest.finish")
                      : t("lessonTest.next")}{" "}
                    →
                  </Button>
                </div>
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>

        <p className="mt-4 text-center text-[11px] text-faint">
          {t("lessonTest.hintKeys", { max: q.options.length })}
        </p>
      </div>
    );
  }

  // --------------------------------------------------------------- result ---
  const answeredList = prepared
    .map((q) => answers[q.slug])
    .filter((a): a is Answer => a != null);
  const correctCount = answeredList.filter((a) => a.correct).length;
  const total = answeredList.length;
  const pct = scorePct(answeredList);
  const missed = answeredList.filter((a) => !a.correct);

  const verdictKey =
    pct === 100
      ? "perfect"
      : pct >= 80
        ? "resultGood"
        : pct >= 40
          ? "resultMid"
          : "resultLow";

  return (
    <div className="mx-auto max-w-2xl">
      <div className="text-center">
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
          {t("lessonTest.resultTitle")}
        </h1>
        <div className="relative mt-6 flex flex-col items-center gap-3">
          {pct === 100 && <CelebrateBurst />}
          <ScoreGauge score={pct} size={120} />
          <p className="text-lg font-semibold text-ink">
            {t("lessonTest.score", { correct: correctCount, total })}
          </p>
          <p className="text-sm text-muted">{t(`lessonTest.${verdictKey}`)}</p>
          {record.isPending && <Spinner />}
          {record.isError && (
            <p className="text-sm text-danger">{t("lessonTest.savingError")}</p>
          )}
        </div>
      </div>

      {missed.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wide text-faint">
            {t("lessonTest.missedTitle")} · {missed.length}
          </h2>
          <div className="space-y-3">
            {missed.map((a) => (
              <div
                key={a.slug}
                className="rounded-2xl border border-border bg-surface p-4 shadow-card"
              >
                <div className="text-[11px] font-bold uppercase tracking-wide text-faint">
                  {a.conceptTitle}
                </div>
                <div className="prose-sm mt-1">
                  <Markdown markdown={a.text} />
                </div>
                <div className="mt-3 space-y-1.5 text-sm">
                  <div className="flex items-start gap-2 text-danger">
                    <span className="shrink-0 font-bold">✗</span>
                    <span>
                      <span className="text-faint">{t("lessonTest.yourAnswer")}: </span>
                      {a.pickedLabel}
                    </span>
                  </div>
                  <div className="flex items-start gap-2 text-success">
                    <span className="shrink-0 font-bold">✓</span>
                    <span>
                      <span className="text-faint">
                        {t("lessonTest.correctAnswer")}:{" "}
                      </span>
                      {a.correctLabel}
                    </span>
                  </div>
                </div>
                {a.explanationMd && (
                  <div className="prose-sm mt-3 border-t border-border pt-3 text-muted">
                    <Markdown markdown={a.explanationMd} />
                  </div>
                )}
                <Link
                  to={`${lessonPath}#${a.anchor}`}
                  className="mt-3 inline-block text-xs font-semibold text-primary hover:underline"
                >
                  {t("lessonTest.toTheory")} →
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button onClick={() => start()}>
          <IconRefresh className="h-4 w-4" />
          {t("lessonTest.retry")}
        </Button>
        {missed.length > 0 && (
          <Button
            variant="secondary"
            onClick={() => start(missed.map((a) => a.slug))}
          >
            {t("lessonTest.retryMistakes")} · {missed.length}
          </Button>
        )}
        <Link to={lessonPath}>
          <Button variant="ghost">{t("lessonTest.toLesson")}</Button>
        </Link>
      </div>
    </div>
  );
}
