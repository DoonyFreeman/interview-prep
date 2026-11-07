import { beforeAll, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import i18n from "../i18n";
import { Markdown } from "../components/Markdown";

// Highlighting has its own tests and depends on the browser theme provider.
vi.mock("../components/ShikiCode", () => ({
  ShikiCode: ({ code }: { code: string }) => createElement("pre", null, code),
}));

beforeAll(async () => { await i18n.changeLanguage("ru"); });
const render = (markdown: string) => renderToStaticMarkup(createElement(Markdown, { markdown }));
const trace = {
  title: "Заказ 42", nodes: ["START", "check", "END"],
  steps: [
    { node: "START", explanation: "Вход", state: { attempts: 0, documents: [] } },
    { node: "check", explanation: "Проверили", state: { attempts: 1, documents: ["policy"] } },
    { node: "END", explanation: "Готово", state: { attempts: 1, documents: ["policy"] } },
  ],
};

describe("lesson teaching blocks", () => {
  it("renders an authored solution as a closed native disclosure, preserving Markdown", () => {
    const html = render('```solution\n**TP = 2**, потому что найдено два спама.\n```');
    expect(html).toContain('<details class="lesson-solution">');
    expect(html).toContain("<summary>Показать решение</summary>");
    expect(html).toContain("<strong>TP = 2</strong>");
    expect(html).not.toMatch(/<details[^>]*\bopen(?:=|>)/);
  });

  it("renders the first trace state with bounded navigation and all named nodes", () => {
    const html = render('```execution\n' + JSON.stringify(trace) + '\n```');
    expect(html).toContain('aria-label="Заказ 42"');
    expect(html).toContain('aria-current="step"');
    expect(html).toContain("attempts");
    expect(html).toContain("Следующий шаг");
    expect(html).toContain("Сначала");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Назад/);
    expect(html).toContain("Заранее заданный пример");
  });

  it.each([
    "{", "null", "[]", '{"title":"x","nodes":[],"steps":[]}',
    JSON.stringify({ ...trace, steps: [{ ...trace.steps[0], node: "missing" }] }),
    JSON.stringify({ ...trace, steps: [{ ...trace.steps[0], state: null }] }),
    JSON.stringify({ ...trace, steps: [{ ...trace.steps[0], state: { nested:
      Array.from({ length: 12 }).reduce<unknown>((v) => [v], "too deep"),
    } }] }),
  ])("keeps malformed trace data from crashing the reader: %s", (source) => {
    expect(render('```execution\n' + source + '\n```')).toContain("Не удалось показать пример");
  });

  it("escapes trace labels and values instead of interpreting HTML", () => {
    const source = { ...trace, title: '<script>alert(1)</script>', steps: [
      { ...trace.steps[0], state: { answer: '<img src=x onerror="alert(1)">' } },
    ] };
    const html = render('```execution\n' + JSON.stringify(source) + '\n```');
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img src=x");
    expect(html).toContain("&lt;img");
  });

  it("keeps ordinary fenced code out of teaching disclosures", () => {
    expect(render('```python\nprint(42)\n```')).not.toContain("lesson-solution");
  });
});
