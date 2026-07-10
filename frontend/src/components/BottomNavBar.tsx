import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  IconCourses,
  IconGlossary,
  IconProgress,
  IconRoadmap,
  IconUser,
} from "./icons";

type Item = {
  to: string;
  end?: boolean;
  labelKey: string;
  Icon: (props: { className?: string }) => React.ReactElement;
};

const ITEMS: Item[] = [
  { to: "/", end: true, labelKey: "nav.courses", Icon: IconCourses },
  { to: "/roadmap", labelKey: "nav.roadmap", Icon: IconRoadmap },
  { to: "/glossary", labelKey: "nav.glossary", Icon: IconGlossary },
  { to: "/progress", labelKey: "nav.progress", Icon: IconProgress },
  { to: "/settings", labelKey: "nav.profile", Icon: IconUser },
];

/**
 * Mobile-only bottom tab bar. Hidden on sm+ (desktop keeps the header nav).
 * Fixed to the bottom, respects the iOS home-bar safe area, and mirrors the
 * primary destinations from the desktop header (review is reached from the
 * dashboard CTA).
 */
export function BottomNavBar() {
  const { t } = useTranslation();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-bg/95 backdrop-blur sm:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label={t("nav.courses")}
    >
      <ul className="mx-auto flex max-w-md">
        {ITEMS.map(({ to, end, labelKey, Icon }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex h-14 flex-col items-center justify-center gap-1 text-[11px] font-semibold transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-muted hover:text-ink active:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <motion.span
                    animate={{ scale: isActive ? 1.12 : 1, y: isActive ? -1 : 0 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  >
                    <Icon
                      className={`h-[22px] w-[22px] ${
                        isActive ? "stroke-[2.4]" : "stroke-2"
                      }`}
                    />
                  </motion.span>
                  <span className="leading-none">{t(labelKey)}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
