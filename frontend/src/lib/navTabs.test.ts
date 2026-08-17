import { beforeEach, describe, it, expect } from "vitest";
import {
  DEFAULT_NAV_TABS,
  MAX_NAV_TABS,
  MIN_NAV_TABS,
  NAV_TABS,
  NAV_TAB_IDS,
  setNavTabs,
  type NavTabId,
} from "./navTabs";

// The store reads localStorage once at import time, so these exercise the
// setter's invariants rather than the initial parse. The suite runs in node, so
// stand a minimal localStorage up first (the module writes through it).
const KEY = "nav_tabs_v1";
const store = new Map<string, string>();
const read = (): NavTabId[] => JSON.parse(store.get(KEY) ?? "[]");

describe("nav tab preference", () => {
  beforeEach(() => {
    store.clear();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    };
  });

  it("defaults to a bar that fits a phone", () => {
    expect(DEFAULT_NAV_TABS.length).toBeLessThanOrEqual(MAX_NAV_TABS);
    expect(DEFAULT_NAV_TABS.length).toBeGreaterThanOrEqual(MIN_NAV_TABS);
  });

  it("every selectable id has a route and a label", () => {
    for (const id of NAV_TAB_IDS) {
      expect(NAV_TABS[id].to.startsWith("/")).toBe(true);
      expect(NAV_TABS[id].labelKey).toMatch(/^nav\./);
    }
  });

  it("stores the canonical order, not the click order", () => {
    setNavTabs(["progress", "courses", "tests"]);
    expect(read()).toEqual(["courses", "tests", "progress"]);
  });

  it("refuses to shrink the bar below the minimum", () => {
    setNavTabs(["courses", "tests", "progress"]);
    setNavTabs(["courses"]);
    expect(read()).toEqual(["courses", "tests", "progress"]);
  });

  it("refuses to overflow the bar", () => {
    setNavTabs(["courses", "tests", "progress"]);
    setNavTabs([...NAV_TAB_IDS]); // 7 — one over the cap
    expect(read()).toEqual(["courses", "tests", "progress"]);
  });

  it("drops duplicates", () => {
    setNavTabs(["courses", "courses", "tests", "progress"]);
    expect(read()).toEqual(["courses", "tests", "progress"]);
  });
});
