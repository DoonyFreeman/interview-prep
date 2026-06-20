import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import type { EvaluationOut } from "../api/types";
import { Markdown } from "./Markdown";
import { ScoreGauge } from "./ScoreGauge";
import { VerdictBadge } from "./VerdictBadge";
import { CelebrateBurst } from "./CelebrateBurst";
import { fadeInUp, staggerContainer } from "../lib/motion";

function Bullets({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "good" | "bad";
}) {
  if (items.length === 0) return null;
  const dot = tone === "good" ? "text-success" : "text-danger";
  return (
    <motion.div variants={fadeInUp}>
      <h4 className="mb-1.5 text-xs font-bold uppercase tracking-wide text-faint">
        {title}
      </h4>
      <ul className="space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-sm text-ink">
            <span className={`mt-0.5 ${dot}`}>{tone === "good" ? "✓" : "•"}</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

export function EvaluationCard({ data }: { data: EvaluationOut }) {
  const { t } = useTranslation();
  const days = Math.max(1, Math.round(data.mastery.interval_days));

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="rounded-2xl border border-border bg-surface p-5 shadow-raised sm:p-6"
    >
      <motion.div variants={fadeInUp} className="flex items-center gap-4">
        <div className="relative shrink-0">
          {data.score === 100 && <CelebrateBurst />}
          <ScoreGauge score={data.score} />
        </div>
        <div className="min-w-0">
          <VerdictBadge verdict={data.verdict} />
          {data.summary && (
            <p className="mt-2 text-sm leading-relaxed text-ink">{data.summary}</p>
          )}
        </div>
      </motion.div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Bullets title={t("quiz.strengths")} items={data.strengths} tone="good" />
        <Bullets title={t("quiz.gaps")} items={data.gaps} tone="bad" />
      </div>

      {data.suggestion && (
        <motion.div
          variants={fadeInUp}
          className="mt-4 rounded-xl bg-primary-soft px-4 py-3 text-sm text-ink"
        >
          <span className="font-semibold">{t("quiz.suggestion")}: </span>
          {data.suggestion}
        </motion.div>
      )}

      {data.reference_answer && (
        <motion.div
          variants={fadeInUp}
          className="mt-4 rounded-xl border border-success/30 bg-success-soft px-4 py-3"
        >
          <h4 className="mb-1.5 text-xs font-bold uppercase tracking-wide text-success">
            {t("quiz.referenceAnswer")}
          </h4>
          <div className="prose-sm text-sm leading-relaxed text-ink">
            <Markdown markdown={data.reference_answer} />
          </div>
        </motion.div>
      )}

      <motion.p
        variants={fadeInUp}
        className="mt-4 flex items-center gap-1.5 text-xs font-medium text-muted"
      >
        <span aria-hidden>↻</span>
        {data.mastery.due
          ? t("quiz.nextReviewToday")
          : t("quiz.nextReviewIn", { count: days })}
      </motion.p>
    </motion.div>
  );
}
