import { describe, expect, it } from "vitest";
import {
  CHEATSHEETS,
  getCheatsheet,
  getCheatsheetSections,
  getLessonCheatsheet,
} from "./cheatsheets";

describe("cheatsheet navigation", () => {
  it("links only the fourth LLM lesson to the ML sheet", () => {
    const sheet = getCheatsheet("ml-metrics");
    expect(sheet).toBeDefined();
    expect(getLessonCheatsheet("llm", "ml-curves-regression")).toBe(sheet);
    expect(getLessonCheatsheet("llm", "ml-classification-metrics")).toBeUndefined();
    expect(getLessonCheatsheet("other-course", "ml-curves-regression")).toBeUndefined();
    expect(getLessonCheatsheet("llm", "agents")).toBeUndefined();
  });

  it("does not manufacture sheets or download URLs from an unknown slug", () => {
    expect(getCheatsheet("../../private")).toBeUndefined();
    expect(getCheatsheet("toString")).toBeUndefined();
    expect(getCheatsheet(undefined)).toBeUndefined();
  });
});

describe("reference sheet sections", () => {
  it("keeps fenced headings and all surrounding content in their section", () => {
    const code = '```python\n## code comment\nprint("hello")\n```';
    const tildeCode = "~~~~text\n## also code\n~~~\n~~~~";
    const sections = getCheatsheetSections(
      `Intro paragraph.\n\n## Первая тема\nBefore.\n\n${code}\nAfter.\n\n${tildeCode}\n\n## Вторая тема\nFinal body.`,
    );
    expect(sections.map((section) => section.title)).toEqual(["", "Первая тема", "Вторая тема"]);
    expect(sections[0].markdown).toBe("Intro paragraph.");
    expect(sections[1].markdown).toContain(code);
    expect(sections[1].markdown).toContain(tildeCode);
    expect(sections[1].markdown).toContain("Before.");
    expect(sections[1].markdown).toContain("After.");
    expect(sections[2].markdown).toBe("Final body.");
  });

  it("gives repeated or punctuation-only headings distinct nonempty anchors", () => {
    const sections = getCheatsheetSections("## Тема\nA\n## Тема\nB\n## Тема-2\nC\n## !!!\nD\n## !!!\nE");
    const anchors = sections.map((section) => section.anchor);
    expect(anchors[0]).toBe("тема");
    expect(new Set(anchors).size).toBe(sections.length);
    expect(anchors.every((anchor) => anchor.length > 0 && !/\s/.test(anchor))).toBe(true);
    expect(sections.map((section) => section.markdown)).toEqual(["A", "B", "C", "D", "E"]);
    expect(getCheatsheetSections(" \n")).toEqual([]);
  });
});

describe("published library assets", () => {
  it("provides six readable sheets with same-origin PDF download paths", () => {
    expect(CHEATSHEETS).toHaveLength(6);
    expect(new Set(CHEATSHEETS.map((sheet) => sheet.slug)).size).toBe(6);
    for (const sheet of CHEATSHEETS) {
      expect(sheet.pdfUrl).toBe(`/cheatsheets/${sheet.slug}.pdf`);
      expect(sheet.pages).toBe(sheet.slug === "ml-metrics" ? 3 : 1);
      const sections = getCheatsheetSections(sheet.markdown);
      expect(sections.length).toBeGreaterThan(0);
      expect(sections.every((section) => section.markdown.trim().length > 0)).toBe(true);
    }
  });
});
