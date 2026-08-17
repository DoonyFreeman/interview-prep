import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  useLessonTest,
  useLessonTestProgress,
  useRecordLessonTest,
} from "../api/hooks";
import { PageLoader } from "../components/Spinner";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";
import { TestRunner } from "../components/TestRunner";
import { IconClipboardCheck } from "../components/icons";
import { fade } from "../lib/motion";
import { prepareTest, toResultItems, type PreparedMcq } from "../lib/lessonTest";

export function LessonTestPage() {
  const { t } = useTranslation();
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const test = useLessonTest(courseSlug, lessonSlug);
  const priorProgress = useLessonTestProgress(courseSlug, lessonSlug);
  const record = useRecordLessonTest(courseSlug, lessonSlug);

  const lessonPath = `/courses/${courseSlug}/lessons/${lessonSlug}`;
  const [prepared, setPrepared] = useState<PreparedMcq[] | null>(null);

  function start(onlySlugs?: string[]) {
    const q = prepareTest(test.data?.questions ?? [], {
      ...(onlySlugs ? { onlySlugs } : {}),
      // Every question here is from the lesson in the URL, so the API doesn't
      // repeat it per question — fill the origin in for the "to theory" links.
      origin: { courseSlug, lessonSlug },
    });
    if (q.length > 0) setPrepared(q);
  }

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

  // ------------------------------------------------------------ run/result ---
  if (prepared) {
    return (
      <TestRunner
        prepared={prepared}
        onFinish={(answers) => {
          const items = toResultItems(answers);
          if (items.length) record.mutate(items);
        }}
        exitTo={lessonPath}
        exitLabel={t("lessonTest.toLesson")}
        onRetry={() => start()}
        onRetryMistakes={(slugs) => start(slugs)}
        saving={record.isPending}
        saveError={record.isError}
      />
    );
  }

  // ---------------------------------------------------------------- intro ---
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
