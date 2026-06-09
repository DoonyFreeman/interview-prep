import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  IconCourses,
  IconGlossary,
  IconProgress,
  IconSlang,
} from "./icons";

type Item = {
  to: string;
  end?: boolean;
  labelKey: string;
  Icon: (props: { className?: string }) => React.ReactElement;
};

const ITEMS: Item[] = [
  { to: "/", end: true, labelKey: "nav.courses", Icon: IconCourses },
  { to: "/glossary", labelKey: "nav.glossary", Icon: IconGlossary },
  { to: "/slang", labelKey: "nav.slang", Icon: IconSlang },
  { to: "/progress", labelKey: "nav.progress", Icon: IconProgress },
];

/**
 * Mobile-only bottom tab bar. Hidden on sm+ (desktop keeps the header nav).
 * Fixed to the bottom, respects the iOS home-bar safe area, and mirrors the
 * four primary destinations from the desktop header.
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
                  <Icon
                    className={`h-[22px] w-[22px] ${
                      isActive ? "stroke-[2.4]" : "stroke-2"
                    }`}
                  />
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
