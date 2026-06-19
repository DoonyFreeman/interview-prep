import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import type { CatThought } from "../lib/cat";

interface Props {
  name: string;
  thought: CatThought | null;
  streak: number;
  onClose: () => void;
  onHide: () => void;
}

export function ThoughtBubble({ name, thought, streak, onClose, onHide }: Props) {
  const { t } = useTranslation();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92, y: 6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.92, y: 6 }}
      transition={{ type: "spring", stiffness: 420, damping: 26 }}
      style={{ transformOrigin: "bottom right" }}
      className="absolute bottom-full right-0 mb-2 w-72 max-w-[78vw] rounded-2xl border border-border bg-surface p-3.5 text-left shadow-pop"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 text-xs font-semibold">
          <span className="truncate font-display text-ink">{name}</span>
          <span className="inline-flex shrink-0 items-center gap-0.5 text-accent">
            <span aria-hidden>🔥</span>
            {t("cat.streakDays", { count: streak })}
          </span>
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={onHide}
            title={t("cat.hide")}
            className="rounded-md px-1.5 text-xs font-semibold text-faint transition-colors hover:text-muted"
          >
            {t("cat.hide")}
          </button>
          <button
            onClick={onClose}
            aria-label="close"
            className="flex h-5 w-5 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            ✕
          </button>
        </div>
      </div>

      {thought ? (
        <>
          <p className="mb-0.5 font-display text-[15px] font-bold leading-snug text-ink">
            {thought.term}
          </p>
          {thought.definition && (
            <p className="mb-2.5 text-sm leading-relaxed text-muted">
              {thought.definition}
            </p>
          )}
          <Link
            to={`/courses/${thought.link.course_slug}/lessons/${thought.link.lesson_slug}#${thought.link.anchor}`}
            onClick={onClose}
            className="inline-flex items-center gap-1 text-sm font-semibold text-primary transition-colors hover:text-primary/80"
          >
            {t("cat.read")} →
          </Link>
        </>
      ) : (
        <p className="text-sm leading-relaxed text-muted">{t("cat.emptyThought")}</p>
      )}
    </motion.div>
  );
}
