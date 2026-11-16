import { memo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AssistantMessage, AssistantSource } from "../api/assistant";
import { IconArticle, IconGlobe, IconSparkles } from "./icons";

const LESSON_LINK = /^\/courses\/[a-z0-9_-]+\/lessons\/[a-z0-9_-]+(?:#[^\s]*)?$/;

function safeSource({ kind, url }: AssistantSource): boolean {
  if (kind === "lesson") return url === "/review" || LESSON_LINK.test(url);
  if (kind !== "web" || !url.startsWith("https://")) return false;
  try {
    const parsed = new URL(url);
    return !!parsed.hostname && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

const activityKeys = {
  search_lessons: "assistant.activity.search_lessons",
  read_lesson_section: "assistant.activity.read_lesson_section",
  get_review_queue: "assistant.activity.get_review_queue",
  web_search: "assistant.activity.web_search",
} as const;

export const AssistantAnswer = memo(function AssistantAnswer({ message }: { message: AssistantMessage }) {
  const { t } = useTranslation();
  const sources = [...new Map(message.sources.filter(safeSource).map((source) => [source.url, source])).values()];
  const byUrl = new Map(sources.map((source) => [source.url, source]));
  const activity = [...new Set(message.tool_activity)].filter((item) => Object.hasOwn(activityKeys, item));

  return (
    <div className="flex min-w-0 gap-3">
      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
        <IconSparkles className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="mb-2 text-sm font-semibold">{t("assistant.title")}</p>
        {activity.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted" aria-label={t("assistant.activity.label")}>
            {activity.map((item) => <li key={item}>{t(activityKeys[item])}</li>)}
          </ul>
        )}
        <div className="prose assistant-answer-text max-w-none">
          <ReactMarkdown
            skipHtml
            disallowedElements={["img"]}
            remarkPlugins={[remarkGfm]}
            components={{
              a({ href, children }) {
                const source = href ? byUrl.get(href) : undefined;
                if (!source) return <>{children}</>;
                return source.kind === "lesson"
                  ? <Link to={source.url}>{children}</Link>
                  : <a href={source.url} target="_blank" rel="noopener noreferrer">{children}</a>;
              },
              table({ children }) {
                return <div className="table-scroll"><table>{children}</table></div>;
              },
            }}
          >
            {message.text}
          </ReactMarkdown>
        </div>
        {sources.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <p className="mb-2 text-xs font-semibold text-muted">{t("assistant.sources")}</p>
            <ul className="flex flex-wrap gap-2">
              {sources.map((source) => {
                const className = "inline-flex min-h-10 max-w-full items-center gap-2 rounded-xl border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-primary-soft hover:text-primary [overflow-wrap:anywhere]";
                return (
                  <li key={source.url} className="max-w-full">
                    {source.kind === "lesson" ? (
                      <Link to={source.url} className={className}>
                        <IconArticle className="size-3.5 shrink-0 text-primary" /> {source.title}
                      </Link>
                    ) : (
                      <a href={source.url} target="_blank" rel="noopener noreferrer" className={className}>
                        <IconGlobe className="size-3.5 shrink-0 text-primary" /> {source.title} <span aria-hidden>↗</span>
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
});
