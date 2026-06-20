import type { ReactNode } from "react";
import { motion } from "motion/react";

/**
 * A friendly empty/zero state: a glyph, a title, an optional hint and an
 * optional action slot. Used for "nothing to review", "no results", etc.
 */
export function EmptyState({
  icon = "✨",
  title,
  hint,
  tone = "neutral",
  children,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  /** `celebrate` tints the glyph teal for "all done" moments. */
  tone?: "neutral" | "celebrate";
  children?: ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-2xl border border-border bg-surface p-10 text-center shadow-card"
    >
      <div
        className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl text-2xl ${
          tone === "celebrate"
            ? "bg-celebrate/15 text-celebrate"
            : "bg-surface-2"
        }`}
      >
        {icon}
      </div>
      <p className="mt-4 font-display text-lg font-bold text-ink">{title}</p>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
      {children && <div className="mt-5 flex justify-center gap-2">{children}</div>}
    </motion.div>
  );
}
