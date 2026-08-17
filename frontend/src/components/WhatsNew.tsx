import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button } from "./Button";
import { IconSparkles } from "./icons";
import {
  markWhatsNewSeen,
  shouldShowWhatsNew,
} from "../lib/whatsNew";

interface Item {
  title: string;
  body: string;
}

/**
 * A one-time release note. Appears on the first visit after an update and never
 * again once dismissed — so it can afford to be a dialog rather than a banner
 * competing for space forever.
 *
 * Mounted in the authenticated shell, so it only greets people who are actually
 * using the app.
 */
export function WhatsNew() {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);

  // Decide after mount: reading localStorage during render would make the first
  // paint depend on storage, and in private mode it throws.
  useEffect(() => {
    if (shouldShowWhatsNew()) setOpen(true);
  }, []);

  function close() {
    markWhatsNewSeen();
    setOpen(false);
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // i18next returns the array as-is with returnObjects; guard anyway so a
  // malformed translation can't blank the screen.
  const raw = t("whatsNew.items", { returnObjects: true });
  const items: Item[] = Array.isArray(raw) ? (raw as Item[]) : [];

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={close}
        >
          <div className="absolute inset-0 bg-black/50" />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={t("whatsNew.title")}
            initial={
              reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 16 }
            }
            animate={reduce ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 16 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className="glass glass-pop relative w-full max-w-md rounded-t-3xl border border-border p-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:rounded-2xl sm:pb-6"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-celebrate" aria-hidden>
                <IconSparkles className="h-6 w-6" />
              </span>
              <h2 className="font-display text-xl font-bold tracking-tight text-ink">
                {t("whatsNew.title")}
              </h2>
            </div>
            <p className="mt-1.5 text-sm text-muted">{t("whatsNew.subtitle")}</p>

            <ul className="mt-5 space-y-3.5">
              {items.map((item, i) => (
                <motion.li
                  key={i}
                  initial={reduce ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.06 + i * 0.05, duration: 0.22 }}
                  className="flex gap-3"
                >
                  <span
                    aria-hidden
                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-ink">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-sm text-muted">
                      {item.body}
                    </span>
                  </span>
                </motion.li>
              ))}
            </ul>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Link to="/tests" onClick={close}>
                <Button>{t("whatsNew.cta")} →</Button>
              </Link>
              <Button variant="ghost" onClick={close}>
                {t("whatsNew.dismiss")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
