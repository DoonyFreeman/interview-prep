import { useTranslation } from "react-i18next";
import { motion } from "motion/react";

const LANGS = ["ru", "en"] as const;

/**
 * RU/EN segmented switch. The filled pill is a shared-layout element, so it
 * *glides* between the two options instead of snapping — same `layoutId`
 * technique and spring as the desktop nav pill in `Layout`, so the two read
 * as one motion language.
 */
export function LanguageToggle() {
  const { i18n } = useTranslation();
  const current = i18n.resolvedLanguage ?? "ru";

  return (
    <div className="inline-flex overflow-hidden rounded-[10px] border border-border bg-surface text-xs font-semibold">
      {LANGS.map((lng) => {
        const active = current.startsWith(lng);
        return (
          <button
            key={lng}
            onClick={() => i18n.changeLanguage(lng)}
            aria-pressed={active}
            className="relative px-2.5 py-1 uppercase transition-colors"
          >
            {active && (
              <motion.span
                layoutId="lang-pill"
                className="absolute inset-0 bg-primary"
                transition={{ type: "spring", stiffness: 480, damping: 38 }}
              />
            )}
            <span
              className={`relative ${
                active ? "text-primary-fg" : "text-muted hover:text-ink"
              }`}
            >
              {lng}
            </span>
          </button>
        );
      })}
    </div>
  );
}
