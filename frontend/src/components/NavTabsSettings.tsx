import { useTranslation } from "react-i18next";
import {
  MAX_NAV_TABS,
  MIN_NAV_TABS,
  NAV_TABS,
  NAV_TAB_IDS,
  setNavTabs,
  useNavTabs,
} from "../lib/navTabs";

/**
 * Pick which sections the mobile bottom bar shows. Desktop keeps the full
 * header nav, so this only matters on a phone — but it's shown everywhere,
 * since people configure their phone from their laptop.
 */
export function NavTabsSettings() {
  const { t } = useTranslation();
  const tabs = useNavTabs();

  const atMax = tabs.length >= MAX_NAV_TABS;
  const atMin = tabs.length <= MIN_NAV_TABS;

  return (
    <div>
      <p className="mb-3 text-xs text-faint">
        {t("settings.navTabsHint", { min: MIN_NAV_TABS, max: MAX_NAV_TABS })}
      </p>
      <div className="flex flex-wrap gap-2">
        {NAV_TAB_IDS.map((id) => {
          const on = tabs.includes(id);
          // A toggle that can't fire is disabled rather than silently ignored.
          const locked = on ? atMin : atMax;
          return (
            <button
              key={id}
              aria-pressed={on}
              disabled={locked}
              onClick={() =>
                setNavTabs(on ? tabs.filter((x) => x !== id) : [...tabs, id])
              }
              className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                on
                  ? "border-primary/40 bg-primary-soft text-primary"
                  : "border-border bg-surface text-muted hover:bg-surface-2"
              }`}
            >
              {t(NAV_TABS[id].labelKey)}
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-xs font-semibold text-muted">
        {t("settings.navTabsCount", { count: tabs.length, max: MAX_NAV_TABS })}
      </p>
    </div>
  );
}
