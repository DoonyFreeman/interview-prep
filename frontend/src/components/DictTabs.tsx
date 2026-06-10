import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";

/**
 * Segmented switch between the reference glossary and the slang dictionary.
 * Slang lives under the "Glossary" primary nav item, so this is how you reach
 * it. The active segment has a gliding pill (layoutId).
 */
export function DictTabs() {
  const { t } = useTranslation();
  const tabs = [
    { to: "/glossary", label: t("nav.glossary") },
    { to: "/slang", label: t("nav.slang") },
  ];
  return (
    <div className="inline-flex rounded-xl border border-border bg-surface p-1">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className="relative rounded-lg px-4 py-1.5 text-sm font-semibold"
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <motion.span
                  layoutId="dict-tab"
                  className="absolute inset-0 rounded-lg bg-primary"
                  transition={{ type: "spring", stiffness: 480, damping: 38 }}
                />
              )}
              <span
                className={`relative transition-colors ${
                  isActive ? "text-primary-fg" : "text-muted hover:text-ink"
                }`}
              >
                {tab.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}
