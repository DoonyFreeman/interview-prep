import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "motion/react";
import { IconKeyboard } from "./icons";

function Keys({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs font-semibold text-ink">
      {children}
    </kbd>
  );
}

/**
 * A small "?"-triggered overlay that surfaces the otherwise-hidden keyboard
 * shortcuts (quiz submit, test navigation). The trigger lives in the header.
 */
export function ShortcutsHelp() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Ignore while typing in a field.
      const el = e.target as HTMLElement | null;
      const typing =
        el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
      if (e.key === "Escape") setOpen(false);
      if (e.key === "?" && !typing) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const rows: Array<{ keys: React.ReactNode; label: string }> = [
    {
      keys: (
        <>
          <Keys>⌘</Keys>
          <span className="text-faint">/</span>
          <Keys>Ctrl</Keys>
          <span className="text-faint">+</span>
          <Keys>Enter</Keys>
        </>
      ),
      label: t("shortcuts.quizSubmit"),
    },
    { keys: <Keys>1–9</Keys>, label: t("shortcuts.testPick") },
    {
      keys: (
        <>
          <Keys>Enter</Keys>
          <span className="text-faint">/</span>
          <Keys>Space</Keys>
        </>
      ),
      label: t("shortcuts.testNext"),
    },
    { keys: <Keys>?</Keys>, label: t("shortcuts.openHelp") },
  ];

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title={t("shortcuts.title")}
        aria-label={t("shortcuts.title")}
        className="hidden h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:text-ink sm:flex"
      >
        <IconKeyboard className="h-4 w-4" />
      </button>

      {createPortal(
        <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setOpen(false)}
          >
            {/* Header has its own backdrop-blur; a second one here would
                muddy it, so this scrim just dims. */}
            <div className="absolute inset-0 bg-black/50" />
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label={t("shortcuts.title")}
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ type: "spring", stiffness: 420, damping: 30 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-sm rounded-2xl border border-border bg-surface p-6 shadow-pop"
            >
              <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
                <IconKeyboard className="h-5 w-5 text-primary" />
                {t("shortcuts.title")}
              </h2>
              <ul className="mt-4 space-y-3">
                {rows.map((r, i) => (
                  <li key={i} className="flex items-center justify-between gap-4">
                    <span className="text-sm text-muted">{r.label}</span>
                    <span className="flex shrink-0 items-center gap-1">{r.keys}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </motion.div>
        )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}
