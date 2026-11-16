import { useEffect, useRef, useState, type RefObject } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { assistantThreadOptions, useAssistantThreads, type AssistantThreadSummary } from "../api/assistant";
import { IconArrowLeft, IconClose, IconPencil, IconPlus, IconSearch, IconTrash } from "./icons";

export const assistantThreadLocation = (id: string) => `/assistant?${new URLSearchParams({ thread: id })}`;
export type AssistantThreadAction = { kind: "rename" | "delete"; thread: AssistantThreadSummary };

export function AssistantHistory({ threadId, answeringId, onNew, onAction, drawer }: {
  threadId: string | null;
  answeringId: string | null;
  onNew: () => void;
  onAction: (action: AssistantThreadAction) => void;
  drawer: RefObject<HTMLDialogElement>;
}) {
  const { t, i18n } = useTranslation();
  const [filter, setFilter] = useState("");
  const threads = useAssistantThreads();
  const queryClient = useQueryClient();
  const date = new Intl.DateTimeFormat(i18n.language, { day: "numeric", month: "short" });
  const query = filter.trim().toLocaleLowerCase(i18n.language);
  const shown = (threads.data ?? []).filter(({ title, preview }) =>
    !query || title.toLocaleLowerCase(i18n.language).includes(query) ||
      preview?.toLocaleLowerCase(i18n.language).includes(query)
  );
  const pendingPrefetch = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    function onResize() {
      if (desktop.matches) drawer.current?.close();
    }
    desktop.addEventListener("change", onResize);
    return () => {
      desktop.removeEventListener("change", onResize);
      clearTimeout(pendingPrefetch.current);
    };
  }, [drawer]);

  function prefetch(id: string) {
    clearTimeout(pendingPrefetch.current);
    pendingPrefetch.current = setTimeout(() => {
      void queryClient.prefetchQuery(assistantThreadOptions(id));
    }, 80);
  }

  function history(mobile: boolean) {
    return (
      <>
        <div className="assistant-history-head">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-display text-lg font-bold tracking-tight">{t("assistant.history")}</h2>
            {mobile && (
              <button className="assistant-icon-button" type="button" onClick={() => drawer.current?.close()} aria-label={t("assistant.closeHistory")} autoFocus>
                <IconClose className="size-5" />
              </button>
            )}
          </div>
          <Link to="/assistant" onClick={() => { setFilter(""); onNew(); }} className="assistant-new-chat">
            <IconPlus className="size-[18px]" />
            {t("assistant.newChat")}
          </Link>
          <label className="assistant-history-search">
            <IconSearch className="size-4 shrink-0" />
            <span className="sr-only">{t("assistant.searchChats")}</span>
            <input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={t("assistant.searchChats")} />
          </label>
        </div>
        <div className="assistant-history-scroll">
          {threads.isPending && (
            <div role="status" className="space-y-2 px-1">
              <span className="sr-only">{t("common.loading")}</span>
              {[1, 2, 3].map((key) => <div key={key} className="assistant-history-placeholder" />)}
            </div>
          )}
          {threads.isError && (
            <div className="assistant-history-empty" role="alert">
              <p>{t("assistant.historyError")}</p>
              <button className="mt-2 font-semibold text-primary hover:underline" type="button" onClick={() => void threads.refetch()}>{t("assistant.retry")}</button>
            </div>
          )}
          {threads.isSuccess && shown.length === 0 && (
            <p className="assistant-history-empty">{t(query ? "assistant.noMatches" : "assistant.noChats")}</p>
          )}
          <ul className="space-y-1">
            {shown.map((thread) => (
              <li key={thread.id} className="assistant-history-row" data-active={thread.id === threadId}>
                <Link
                  to={assistantThreadLocation(thread.id)}
                  aria-current={thread.id === threadId ? "page" : undefined}
                  aria-label={thread.title}
                  title={thread.title}
                  onFocus={() => prefetch(thread.id)}
                  onPointerEnter={() => prefetch(thread.id)}
                  onPointerLeave={() => clearTimeout(pendingPrefetch.current)}
                  onClick={() => drawer.current?.close()}
                  className="assistant-history-link"
                >
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span className="min-w-0 flex-1 truncate font-semibold">{thread.title}</span>
                    {answeringId === thread.id && <span className="assistant-activity-dot" title={t("assistant.answering")} />}
                  </div>
                  {thread.preview !== thread.title && (
                    <span className="assistant-history-preview">{thread.preview || t("assistant.noPreview")}</span>
                  )}
                  <time className="assistant-history-date" dateTime={thread.updated_at}>{date.format(new Date(thread.updated_at))}</time>
                </Link>
                <div className="assistant-history-actions">
                  <button type="button" className="assistant-icon-button" title={t("assistant.rename")} aria-label={`${t("assistant.rename")} — ${thread.title}`} disabled={answeringId === thread.id} onClick={() => onAction({ kind: "rename", thread })}>
                    <IconPencil className="size-4" />
                  </button>
                  <button type="button" className="assistant-icon-button assistant-delete-action" title={t("assistant.delete")} aria-label={`${t("assistant.delete")} — ${thread.title}`} disabled={answeringId === thread.id} onClick={() => onAction({ kind: "delete", thread })}>
                    <IconTrash className="size-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="assistant-history-footer">
          <Link to="/" className="assistant-back-link">
            <IconArrowLeft className="size-4 shrink-0" />
            {t("assistant.back")}
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <aside className="assistant-sidebar" aria-label={t("assistant.history")}>{history(false)}</aside>
      <dialog
        id="assistant-mobile-history"
        ref={drawer}
        className="assistant-history-drawer"
        aria-label={t("assistant.history")}
        onClick={(event) => {
          if (event.target === event.currentTarget) drawer.current?.close();
        }}
      >
        <div className="assistant-drawer-content">{history(true)}</div>
      </dialog>
    </>
  );
}
