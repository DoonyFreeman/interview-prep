/**
 * Which sections appear in the mobile bottom bar.
 *
 * There are more worthwhile destinations than a phone tab bar can hold, so the
 * set is the user's choice (edited in Settings) rather than a fixed list. It's a
 * pure client preference — no server round-trip, no account state — so it lives
 * in localStorage and is published through `useSyncExternalStore` so the bar and
 * the settings panel stay in step without a context provider.
 */
import { useSyncExternalStore } from "react";

export const NAV_TAB_IDS = [
  "courses",
  "roadmap",
  "glossary",
  "tests",
  "progress",
  "review",
  "profile",
] as const;

export type NavTabId = (typeof NAV_TAB_IDS)[number];

/** Route + label for each selectable tab. Icons are wired up in the bar itself
 *  so this module stays free of JSX (and so tests can import it). */
export const NAV_TABS: Record<NavTabId, { to: string; end?: boolean; labelKey: string }> =
  {
    courses: { to: "/", end: true, labelKey: "nav.courses" },
    roadmap: { to: "/roadmap", labelKey: "nav.roadmap" },
    glossary: { to: "/glossary", labelKey: "nav.glossary" },
    tests: { to: "/tests", labelKey: "nav.tests" },
    progress: { to: "/progress", labelKey: "nav.progress" },
    review: { to: "/review", labelKey: "nav.review" },
    profile: { to: "/settings", labelKey: "nav.profile" },
  };

export const DEFAULT_NAV_TABS: NavTabId[] = [
  "courses",
  "roadmap",
  "glossary",
  "tests",
  "progress",
  "profile",
];

/** Fewer than this and the bar stops being navigation; more and the labels
 *  stop being readable on a 375px phone. */
export const MIN_NAV_TABS = 3;
export const MAX_NAV_TABS = 6;

const KEY = "nav_tabs_v1";

function parse(raw: string | null): NavTabId[] {
  if (!raw) return DEFAULT_NAV_TABS;
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_NAV_TABS;
    // Drop anything unknown (an id removed in a later version) and de-duplicate.
    const clean = NAV_TAB_IDS.filter((id) => parsed.includes(id));
    return clean.length >= MIN_NAV_TABS ? clean : DEFAULT_NAV_TABS;
  } catch {
    return DEFAULT_NAV_TABS;
  }
}

let current: NavTabId[] = parse(
  typeof localStorage === "undefined" ? null : localStorage.getItem(KEY),
);
const listeners = new Set<() => void>();

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function setNavTabs(ids: NavTabId[]): void {
  // Keep the canonical order regardless of the order they were clicked in, and
  // never let the bar go under the minimum.
  const next = NAV_TAB_IDS.filter((id) => ids.includes(id));
  if (next.length < MIN_NAV_TABS || next.length > MAX_NAV_TABS) return;
  current = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* private mode — the choice just won't survive a reload */
  }
  listeners.forEach((fn) => fn());
}

export function useNavTabs(): NavTabId[] {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => DEFAULT_NAV_TABS,
  );
}
