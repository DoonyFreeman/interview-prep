import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Markdown } from "../components/Markdown";
import { isConceptLink } from "./conceptLinks";

describe("authored concept links", () => {
  it("accepts an internal lesson section with a plain definition", () => {
    expect(isConceptLink("/courses/python-core/lessons/01-gil#что-такое-gil", "Определение")).toBe(true);
  });

  it.each([
    undefined, "", "/courses/python-core/lessons/01-gil", "/courses/python-core/lessons/01-gil#",
    "https://example.com/courses/python-core/lessons/01-gil#gil",
    "//example.com/courses/python-core/lessons/01-gil#gil",
    "/courses/python-core/lessons/01-gil?next=1#gil",
    "/courses/python-core/lessons/01-gil#two words",
    "/courses/python-core/lessons/01-gil#gil#other",
    "javascript:alert(1)", "/courses/../lessons/01-gil#gil",
  ])("rejects non-section or non-local href %s", (href) => {
    expect(isConceptLink(href, "Definition")).toBe(false);
  });

  it.each([undefined, "", "   "])("requires an authored definition %s", (title) => {
    expect(isConceptLink("/courses/python-core/lessons/01-gil#gil", title)).toBe(false);
  });

  it("keeps a real navigable anchor and a separate preview button inside prose", () => {
    const html = renderToStaticMarkup(createElement(Markdown, {
      markdown: 'Read [GIL](/courses/python-core/lessons/01-gil#gil "One thread at a time") again.',
    }));
    expect(html).toContain('<p>Read <span class="concept-link">');
    expect(html).toContain('href="/courses/python-core/lessons/01-gil#gil"');
    expect(html).toContain('</a><button');
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('role="tooltip"');
  });

  it("preserves external links and internal links without definitions", () => {
    const html = renderToStaticMarkup(createElement(Markdown, {
      markdown: '[External](https://example.com "External title") [Plain](/courses/python-core/lessons/01-gil#gil)',
    }));
    expect(html).toContain('title="External title" target="_blank" rel="noreferrer"');
    expect(html).not.toContain('concept-link');
    expect(html).not.toContain('<button');
  });
});
