import { beforeEach, describe, it, expect } from "vitest";
import {
  DEFAULT_NAV_TABS,
  MAX_NAV_TABS,
  MIN_NAV_TABS,
  NAV_TABS,
  NAV_TAB_IDS,
  setNavTabs,
  parseNavTabs,
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
    setNavTabs(["cheatsheets", "courses", "tests"]);
    expect(read()).toEqual(["courses", "tests", "cheatsheets"]);
  });

  it("refuses to shrink the bar below the minimum", () => {
    setNavTabs(["courses", "tests", "cheatsheets"]);
    setNavTabs(["courses"]);
    expect(read()).toEqual(["courses", "tests", "cheatsheets"]);
  });

  it("refuses to overflow the bar", () => {
    setNavTabs(["courses", "tests", "cheatsheets"]);
    setNavTabs([...NAV_TAB_IDS]); // 7 — one over the cap
    expect(read()).toEqual(["courses", "tests", "cheatsheets"]);
  });

  it("drops duplicates", () => {
    setNavTabs(["courses", "courses", "tests", "cheatsheets"]);
    expect(read()).toEqual(["courses", "tests", "cheatsheets"]);
  });
});


describe("saved navigation migration", () => {
  it("replaces the legacy Progress tab while preserving other selected sections", () => {
    expect(parseNavTabs('["courses","tests","progress","profile"]'))
      .toEqual(["courses", "tests", "cheatsheets", "profile"]);
  });

  it("does not add the library when Progress was not selected", () => {
    expect(parseNavTabs('["courses","tests","review"]'))
      .toEqual(["courses", "tests", "review"]);
  });

  it("deduplicates a preference containing both old and new tab IDs", () => {
    expect(parseNavTabs('["courses","progress","cheatsheets","tests"]'))
      .toEqual(["courses", "tests", "cheatsheets"]);
  });

  it("falls back for corrupted preferences", () => {
    expect(parseNavTabs("not-json")).toEqual(DEFAULT_NAV_TABS);
    expect(parseNavTabs('["progress"]')).toEqual(DEFAULT_NAV_TABS);
  });
});
