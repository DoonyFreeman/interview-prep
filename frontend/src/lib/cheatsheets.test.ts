import { describe, expect, it } from "vitest";
import {
  CHEATSHEETS,
  RAG_CHEATSHEET_BUNDLE,
  getCheatsheetBundle,
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

  it("links each deep RAG lesson to its own sheet without attaching the overview", () => {
    for (const slug of RAG_CHEATSHEET_BUNDLE.slugs.slice(1)) {
      expect(getLessonCheatsheet("llm", slug)).toBe(getCheatsheet(slug));
      expect(getLessonCheatsheet("other-course", slug)).toBeUndefined();
    }
    expect(getLessonCheatsheet("llm", "rag")).toBeUndefined();
    expect(getLessonCheatsheet("llm", "rag-agents")).toBeUndefined();
    expect(getLessonCheatsheet("llm", "llm-basics")).toBeUndefined();
    expect(getLessonCheatsheet("llm", "toString")).toBeUndefined();
    expect(getLessonCheatsheet(undefined, undefined)).toBeUndefined();
  });

  it("offers the ordered RAG bundle only for its four members", () => {
    expect(RAG_CHEATSHEET_BUNDLE.slugs).toEqual([
      "rag", "rag-documents-embeddings", "rag-search-indexes", "rag-evaluation",
    ]);
    expect(RAG_CHEATSHEET_BUNDLE.pdfUrl).toBe("/cheatsheets/rag-all.pdf");
    expect(RAG_CHEATSHEET_BUNDLE.pages).toBe(7);
    const members = RAG_CHEATSHEET_BUNDLE.slugs.map((slug) => getCheatsheet(slug)!);
    expect(members.reduce((pages, sheet) => pages + sheet.pages, 0)).toBe(RAG_CHEATSHEET_BUNDLE.pages);
    expect(CHEATSHEETS.filter((sheet) => sheet.category === "rag").map((sheet) => sheet.slug))
      .toEqual(RAG_CHEATSHEET_BUNDLE.slugs);
    for (const slug of RAG_CHEATSHEET_BUNDLE.slugs) {
      expect(getCheatsheetBundle(slug)).toBe(RAG_CHEATSHEET_BUNDLE);
    }
    for (const slug of ["ml-metrics", "agents", "llm-basics", "../../private", "toString", undefined]) {
      expect(getCheatsheetBundle(slug)).toBeUndefined();
    }
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
  it("provides nine readable sheets with same-origin PDF download paths", () => {
    expect(CHEATSHEETS).toHaveLength(9);
    expect(new Set(CHEATSHEETS.map((sheet) => sheet.slug)).size).toBe(9);
    for (const sheet of CHEATSHEETS) {
      expect(sheet.pdfUrl).toBe(`/cheatsheets/${sheet.slug}.pdf`);
      expect(sheet.pages).toBe(sheet.slug === "ml-metrics" ? 3 : RAG_CHEATSHEET_BUNDLE.slugs.slice(1).some((slug) => slug === sheet.slug) ? 2 : 1);
      const sections = getCheatsheetSections(sheet.markdown);
      expect(sections.length).toBeGreaterThan(0);
      expect(sections.every((section) => section.markdown.trim().length > 0)).toBe(true);
    }
  });
});
