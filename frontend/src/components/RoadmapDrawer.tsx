import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type {
  RoadmapCourse,
  RoadmapExtraNode,
  RoadmapLesson,
  RoadmapResource,
} from "../api/types";
import { resourcesFor, type LessonStatus } from "../lib/roadmap";
import { IconArticle, IconDocs, IconVideo } from "./icons";

export type RoadmapSelection =
  | { kind: "lesson"; course: RoadmapCourse; lesson: RoadmapLesson; status: LessonStatus }
  | { kind: "extra"; node: RoadmapExtraNode };

const RESOURCE_ICONS: Record<
  string,
  (props: { className?: string }) => React.ReactElement
> = {
  video: IconVideo,
  article: IconArticle,
  docs: IconDocs,
};

function ResourceList({
  resources,
  caption,
}: {
  resources: RoadmapResource[];
  caption?: string;
}) {
  const { t } = useTranslation();
  if (resources.length === 0) {
    return <p className="text-sm text-muted">{t("roadmap.noMaterials")}</p>;
  }
  return (
    <>
      {caption && <p className="mb-2 text-xs text-faint">{caption}</p>}
      <ul className="space-y-1">
        {resources.map((res) => {
          const Icon = RESOURCE_ICONS[res.type] ?? IconArticle;
          return (
            <li key={res.url}>
              <a
                href={res.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-start gap-3 rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-surface-2"
              >
                <Icon className="mt-0.5 h-[18px] w-[18px] shrink-0 text-muted" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-ink group-hover:text-primary">
                    {res.title}
                    <span aria-hidden className="ml-1 text-faint">
                      ↗
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">
                    {res.source}
                  </span>
                </span>
                <span
                  className={`mt-0.5 shrink-0 rounded px-1 py-0.5 text-[10px] font-bold uppercase ${
                    res.lang === "ru"
                      ? "bg-primary-soft text-primary"
                      : "bg-surface-2 text-muted"
                  }`}
                >
                  {res.lang}
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </>
  );
}

const STATUS_PILL: Record<LessonStatus, string> = {
  done: "bg-success-soft text-success",
  attempted: "bg-warn-soft text-warn",
  none: "bg-surface-2 text-muted",
};

/**
 * Node detail sheet: bottom sheet on phones, right-side panel on sm+. Same
 * portal/AnimatePresence idiom as SearchModal; Escape and backdrop close.
 */
export function RoadmapDrawer({
  selection,
  onClose,
}: {
  selection: RoadmapSelection | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const reduced = useReducedMotion();
  const closeRef = useRef<HTMLButtonElement>(null);

  // Move focus into the sheet on open; restore it to the opener (the chip) on
  // close so keyboard users don't lose their place in the roadmap. Depends on
  // `selection` only, so a parent re-render while open doesn't yank focus.
  const openerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!selection) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    return () => openerRef.current?.focus?.();
  }, [selection]);

  useEffect(() => {
    if (!selection) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selection, onClose]);

  const title =
    selection?.kind === "lesson" ? selection.lesson.title : selection?.node.title;

  return createPortal(
    <AnimatePresence>
      {selection && (
        <motion.div
          className="fixed inset-0 z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
        >
          <div className="absolute inset-0 bg-black/50" />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={reduced ? { opacity: 0 } : { opacity: 0, y: 24 }}
            animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: 24 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto overscroll-contain rounded-t-2xl border-t border-border bg-surface p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-pop sm:inset-x-auto sm:inset-y-0 sm:right-0 sm:max-h-none sm:w-[420px] sm:rounded-none sm:border-l sm:border-t-0 sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                {selection.kind === "lesson" ? (
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {selection.course.title}
                  </p>
                ) : (
                  <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                    {t("roadmap.externalTopic")}
                  </p>
                )}
                <h2 className="mt-1 font-display text-lg font-bold leading-snug text-ink">
                  {title}
                </h2>
              </div>
              <button
                ref={closeRef}
                onClick={onClose}
                aria-label={t("common.close")}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-ink"
              >
                ✕
              </button>
            </div>

            {selection.kind === "lesson" ? (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_PILL[selection.status]}`}
                  >
                    {t(`roadmap.status.${selection.status}`)}
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-wide text-faint">
                    {selection.lesson.duration_minutes} {t("roadmap.min")}
                  </span>
                </div>

                <Link
                  to={`/courses/${selection.course.slug}/lessons/${selection.lesson.slug}`}
                  className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-fg shadow-card transition hover:bg-primary-strong active:scale-[0.98]"
                >
                  {t("roadmap.openLesson")} →
                </Link>

                <h3 className="mt-6 mb-2 text-xs font-bold uppercase tracking-wide text-muted">
                  {t("roadmap.materials")}
                </h3>
                {(() => {
                  const { resources, fromCourse } = resourcesFor(
                    selection.course,
                    selection.lesson.slug,
                  );
                  return (
                    <ResourceList
                      resources={resources}
                      caption={
                        fromCourse && resources.length > 0
                          ? t("roadmap.courseMaterials")
                          : undefined
                      }
                    />
                  );
                })()}
              </>
            ) : (
              <>
                <p className="mt-3 text-sm leading-relaxed text-muted">
                  {selection.node.summary}
                </p>
                <h3 className="mt-6 mb-2 text-xs font-bold uppercase tracking-wide text-muted">
                  {t("roadmap.materials")}
                </h3>
                <ResourceList resources={selection.node.resources} />
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
