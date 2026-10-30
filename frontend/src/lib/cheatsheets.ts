import concurrency from "../content/cheatsheets/concurrency.md?raw";
import teamProcesses from "../content/cheatsheets/team-processes.md?raw";
import llmBasics from "../content/cheatsheets/llm-basics.md?raw";
import rag from "../content/cheatsheets/rag.md?raw";
import agents from "../content/cheatsheets/agents.md?raw";
import mlMetrics from "../content/cheatsheets/ml-metrics.md?raw";
import { slugify } from "./slugify";

export type CheatsheetCategory = "python" | "team" | "ai";

export interface Cheatsheet {
  slug: string;
  title: string;
  description: string;
  category: CheatsheetCategory;
  pdfUrl: string;
  pages: 1;
  markdown: string;
}

export const CHEATSHEET_GROUPS = [
  { id: "python", labelKey: "cheatsheets.groups.python" },
  { id: "team", labelKey: "cheatsheets.groups.team" },
  { id: "ai", labelKey: "cheatsheets.groups.ai" },
] as const;

export const CHEATSHEETS: readonly Cheatsheet[] = [
  {
    slug: "concurrency",
    title: "Конкурентность в Python",
    description: "GIL, потоки, процессы и asyncio: что выбрать и почему.",
    category: "python",
    pdfUrl: "/cheatsheets/concurrency.pdf",
    pages: 1,
    markdown: concurrency,
  },
  {
    slug: "team-processes",
    title: "Процессы в команде",
    description: "Agile, Scrum, Kanban, Git и code review в одном месте.",
    category: "team",
    pdfUrl: "/cheatsheets/team-processes.pdf",
    pages: 1,
    markdown: teamProcesses,
  },
  {
    slug: "llm-basics",
    title: "Основы LLM",
    description: "Токены, контекст, параметры генерации и работа с промптами.",
    category: "ai",
    pdfUrl: "/cheatsheets/llm-basics.pdf",
    pages: 1,
    markdown: llmBasics,
  },
  {
    slug: "rag",
    title: "RAG: поиск и контекст",
    description: "Эмбеддинги, чанкинг, retrieval, reranking и оценка качества.",
    category: "ai",
    pdfUrl: "/cheatsheets/rag.pdf",
    pages: 1,
    markdown: rag,
  },
  {
    slug: "agents",
    title: "LLM-агенты",
    description: "Инструменты, цикл агента, память и границы автономности.",
    category: "ai",
    pdfUrl: "/cheatsheets/agents.pdf",
    pages: 1,
    markdown: agents,
  },
  {
    slug: "ml-metrics",
    title: "Метрики ML, кривые и регрессия",
    description: "Precision, recall, ROC/PR, пороги и метрики регрессии.",
    category: "ai",
    pdfUrl: "/cheatsheets/ml-metrics.pdf",
    pages: 1,
    markdown: mlMetrics,
  },
];

export function getCheatsheet(slug: string | undefined): Cheatsheet | undefined {
  return CHEATSHEETS.find((sheet) => sheet.slug === slug);
}

export function getLessonCheatsheet(
  courseSlug: string | undefined,
  lessonSlug: string | undefined,
): Cheatsheet | undefined {
  return courseSlug === "llm" && lessonSlug === "ml-curves-regression"
    ? getCheatsheet("ml-metrics")
    : undefined;
}

export interface CheatsheetSection {
  title: string;
  anchor: string;
  markdown: string;
}

/** Split at H2s, keeping fenced code intact and preserving an optional intro. */
export function getCheatsheetSections(markdown: string): CheatsheetSection[] {
  const sections: CheatsheetSection[] = [];
  const anchors = new Set<string>();
  let title = "";
  let lines: string[] = [];
  let fence: { marker: string; length: number } | undefined;

  function append() {
    const body = lines.join("\n").trim();
    if (!title && !body) return;
    const base = slugify(title) || (title ? "section" : "introduction");
    let anchor = base;
    let suffix = 2;
    while (anchors.has(anchor)) anchor = `${base}-${suffix++}`;
    anchors.add(anchor);
    sections.push({ title, anchor, markdown: body });
  }

  for (const line of markdown.replace(/\r\n?/g, "\n").split("\n")) {
    const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
    if (fence) {
      if (marker && marker[1][0] === fence.marker && marker[1].length >= fence.length && !marker[2].trim()) {
        fence = undefined;
      }
      lines.push(line);
      continue;
    }
    if (marker && (marker[1][0] !== "`" || !marker[2].includes("`"))) {
      fence = { marker: marker[1][0], length: marker[1].length };
      lines.push(line);
      continue;
    }
    const heading = /^ {0,3}##[\t ]+(.+?)[\t ]*$/.exec(line);
    if (heading) {
      append();
      title = heading[1].replace(/[\t ]+#+[\t ]*$/, "");
      lines = [];
    } else {
      lines.push(line);
    }
  }
  append();
  return sections;
}
