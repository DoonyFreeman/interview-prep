import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  IconClipboardCheck,
  IconCourses,
  IconGlossary,
  IconProgress,
  IconRefresh,
  IconRoadmap,
  IconUser,
} from "./icons";
import { NAV_TABS, useNavTabs, type NavTabId } from "../lib/navTabs";

const ICONS: Record<NavTabId, (props: { className?: string }) => React.ReactElement> = {
  courses: IconCourses,
  roadmap: IconRoadmap,
  glossary: IconGlossary,
  tests: IconClipboardCheck,
  progress: IconProgress,
  review: IconRefresh,
  profile: IconUser,
};

/**
 * Mobile-only bottom tab bar. Hidden on sm+ (desktop keeps the header nav).
 * A *floating glass island* rather than an edge-to-edge strip: it sits clear
 * of the iOS home bar and content scrolls visibly beneath it. Which
 * destinations it shows is the user's choice (Settings → nav tabs), because
 * there are more of them than fit on a phone.
 */
export function BottomNavBar() {
  const { t } = useTranslation();
  const tabs = useNavTabs();
  // Six labels at 11px overflow a 375px screen; five and under have room.
  const tight = tabs.length > 5;

  return (
    <nav
      className="fixed inset-x-0 z-30 px-3 sm:hidden"
      style={{ bottom: "calc(env(safe-area-inset-bottom) + 0.5rem)" }}
      aria-label={t("nav.courses")}
    >
      <ul className="glass mx-auto flex max-w-sm overflow-hidden rounded-[26px] border border-border">
        {tabs.map((id) => {
          const { to, end, labelKey } = NAV_TABS[id];
          const Icon = ICONS[id];
          return (
            <li key={id} className="min-w-0 flex-1">
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex h-14 flex-col items-center justify-center gap-1 px-0.5 font-semibold transition-colors ${
                    tight ? "text-[10px]" : "text-[11px]"
                  } ${
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
                        className={`${tight ? "h-5 w-5" : "h-[22px] w-[22px]"} ${
                          isActive ? "stroke-[2.4]" : "stroke-2"
                        }`}
                      />
                    </motion.span>
                    <span className="w-full truncate text-center leading-none">
                      {t(labelKey)}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
