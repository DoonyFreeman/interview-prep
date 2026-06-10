import { useTranslation } from "react-i18next";
import { motion } from "motion/react";

/** Maps the backend's Russian verdict string to a style + localized label. */
const MAP: Record<string, { key: string; cls: string }> = {
  верно: { key: "quiz.verdict.correct", cls: "bg-success-soft text-success" },
  частично: { key: "quiz.verdict.partial", cls: "bg-warn-soft text-warn" },
  неверно: { key: "quiz.verdict.wrong", cls: "bg-danger-soft text-danger" },
};

export function VerdictBadge({ verdict }: { verdict: string }) {
  const { t } = useTranslation();
  const entry = MAP[verdict] ?? MAP["частично"];
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 420, damping: 22, delay: 0.1 }}
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${entry.cls}`}
    >
      {t(entry.key)}
    </motion.span>
  );
}
