import { motion } from "motion/react";

export function ProgressBar({
  value,
  total,
  pct,
  className = "",
  tone = "primary",
}: {
  value?: number;
  total?: number;
  /** Pass a precomputed percentage (0–100) instead of value/total. */
  pct?: number;
  className?: string;
  /** Bar colour — `celebrate` once a track is fully complete. */
  tone?: "primary" | "celebrate";
}) {
  const percent =
    pct != null
      ? Math.max(0, Math.min(100, Math.round(pct)))
      : total && total > 0
        ? Math.round(((value ?? 0) / total) * 100)
        : 0;
  const bar = tone === "celebrate" ? "bg-celebrate" : "bg-primary";
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-border ${className}`}>
      <motion.div
        className={`h-2 rounded-full ${bar}`}
        initial={{ width: 0 }}
        animate={{ width: `${percent}%` }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  );
}
