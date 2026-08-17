import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button } from "./Button";
import { Markdown } from "./Markdown";
import { ScoreGauge } from "./ScoreGauge";
import { Spinner } from "./Spinner";
import { CelebrateBurst } from "./CelebrateBurst";
import { IconRefresh } from "./icons";
import { fade } from "../lib/motion";
import {
  scorePct,
  theoryPath,
  type Answer,
  type PreparedMcq,
} from "../lib/lessonTest";

interface Props {
  /** The run, already shuffled (see `prepareTest`). */
  prepared: PreparedMcq[];
  /** Called once, when the last question is answered and the run is scored. */
  onFinish: (answers: Answer[]) => void;
  /**
   * Leaving the run — the ✕ during a run and the last button on the result.
   *
   * Pass `exitTo` when the exit is a real navigation (the per-lesson test goes
   * back to its lesson) and `onExit` when it returns to an earlier phase of the
   * *same* route (the mixed test goes back to its setup panel). The distinction
   * matters: a `<Link>` to the path you are already on is a no-op, so the mixed
   * test's exit silently did nothing.
   */
  exitTo?: string;
  onExit?: () => void;
  exitLabel: string;
  /** Start the same kind of run again with a fresh draw. */
  onRetry: () => void;
  /** Re-run only the questions that were missed. */
  onRetryMistakes: (slugs: string[]) => void;
  /** Show each question's course › lesson — useful only when a run spans them. */
  showOrigin?: boolean;
  saving?: boolean;
  saveError?: boolean;
}

/**
 * The MCQ runner: one question at a time, instant reveal, then a scored result
 * with every miss explained. Shared by the per-lesson self-test and the mixed
 * `/tests` section — they differ only in how the questions were chosen, not in
 * how they're answered, so the whole run/result experience lives here.
 *
 * Grading is a plain index compare (the API ships `correct_index` for MCQ by
 * design); this component owns no data fetching.
 */
/**
 * The exit control, rendered as whichever element actually works: an anchor
 * when there is somewhere to navigate to, a button when the caller just needs
 * to change its own state.
 */
function Exit({
  to,
  onExit,
  className,
  ariaLabel,
  children,
}: {
  to?: string;
  onExit?: () => void;
  className?: string;
  ariaLabel?: string;
  children: React.ReactNode;
}) {
  if (onExit) {
    return (
      <button type="button" onClick={onExit} className={className} aria-label={ariaLabel}>
        {children}
      </button>
    );
  }
  return (
    <Link to={to ?? "/"} className={className} aria-label={ariaLabel}>
      {children}
    </Link>
  );
}

export function TestRunner({
  prepared,
  onFinish,
  exitTo,
  onExit,
  exitLabel,
  onRetry,
  onRetryMistakes,
  showOrigin = false,
  saving = false,
  saveError = false,
}: Props) {
  const { t } = useTranslation();
  const reduce = useReducedMotion();

  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [picked, setPicked] = useState<number | null>(null);
  const [done, setDone] = useState(false);
  const finished = useRef(false);

  // A new run (different array identity) resets everything.
  useEffect(() => {
    setIndex(0);
    setAnswers({});
    setPicked(null);
    setDone(false);
    finished.current = false;
  }, [prepared]);

  function choose(optIndex: number) {
    if (picked != null) return;
    const q = prepared[index];
    const opt = q?.options[optIndex];
    if (!q || !opt) return;
    setPicked(optIndex);
    setAnswers((a) => ({
      ...a,
      [q.slug]: {
        slug: q.slug,
        conceptTitle: q.conceptTitle,
        anchor: q.anchor,
        courseSlug: q.courseSlug,
        lessonSlug: q.lessonSlug,
        courseTitle: q.courseTitle,
        lessonTitle: q.lessonTitle,
        text: q.text,
        correct: opt.correct,
        pickedLabel: opt.label,
        correctLabel: q.options.find((o) => o.correct)?.label,
        explanationMd: q.explanationMd,
      },
    }));
  }

  function next() {
    if (index + 1 >= prepared.length) setDone(true);
    else {
      setIndex((i) => i + 1);
      setPicked(null);
    }
  }

  // Keyboard: 1–N to pick an option, Enter/Space to advance after the reveal.
  useEffect(() => {
    if (done) return;
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
  }, [done, index, picked, prepared]);

  // Report the finished run exactly once.
  useEffect(() => {
    if (!done || finished.current) return;
    finished.current = true;
    onFinish(prepared.map((q) => answers[q.slug]).filter((a): a is Answer => a != null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done]);

  // ------------------------------------------------------------------ run ---
  if (!done) {
    const q = prepared[index];
    if (!q) return null;
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
              <Exit
                to={exitTo}
                onExit={onExit}
                className="text-muted hover:text-ink"
                ariaLabel={exitLabel}
              >
                ✕
              </Exit>
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
                {showOrigin && q.courseTitle ? (
                  <>
                    {q.courseTitle} <span className="text-border">›</span>{" "}
                    {q.conceptTitle}
                  </>
                ) : (
                  q.conceptTitle
                )}
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
                    to={theoryPath(q)}
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
          {saving && <Spinner />}
          {saveError && (
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
                  {showOrigin && a.courseTitle ? (
                    <>
                      {a.courseTitle} <span className="text-border">›</span>{" "}
                      {a.conceptTitle}
                    </>
                  ) : (
                    a.conceptTitle
                  )}
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
                {theoryPath(a) && (
                  <Link
                    to={theoryPath(a)}
                    className="mt-3 inline-block text-xs font-semibold text-primary hover:underline"
                  >
                    {t("lessonTest.toTheory")} →
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onRetry}>
          <IconRefresh className="h-4 w-4" />
          {t("lessonTest.retry")}
        </Button>
        {missed.length > 0 && (
          <Button
            variant="secondary"
            onClick={() => onRetryMistakes(missed.map((a) => a.slug))}
          >
            {t("lessonTest.retryMistakes")} · {missed.length}
          </Button>
        )}
        {onExit ? (
          <Button variant="ghost" onClick={onExit}>
            {exitLabel}
          </Button>
        ) : (
          <Link to={exitTo ?? "/"}>
            <Button variant="ghost">{exitLabel}</Button>
          </Link>
        )}
      </div>
    </div>
  );
}
