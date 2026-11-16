import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AssistantStreamError,
  assistantThreadKey,
  assistantThreadsKey,
  createAssistantThread,
  deleteAssistantThread,
  sendAssistantTurn,
  useAssistantConfig,
  useAssistantThread,
  useAssistantThreads,
  type AssistantLesson,
  type AssistantPhase,
  type AssistantTurn,
} from "../api/assistant";
import { useProgress } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { AssistantAnswer } from "../components/AssistantAnswer";
import { Button } from "../components/Button";
import {
  IconArrowUp,
  IconArticle,
  IconGlobe,
  IconHistory,
  IconPlus,
  IconSparkles,
  IconTarget,
  IconTrash,
} from "../components/icons";
import { Spinner } from "../components/Spinner";
import { getToken } from "../lib/token";
import "./assistant.css";

const slugPattern = /^[a-z0-9_-]+$/;
const MAX_MESSAGE_LENGTH = 3000;
const threadLocation = (id: string) => `/assistant?${new URLSearchParams({ thread: id })}`;
const turnErrors: Record<string, string> = {
  assistant_busy: "assistant.busy",
  assistant_rate_limit: "assistant.rateLimit",
  assistant_thread_limit: "assistant.threadLimit",
  assistant_turn_limit: "assistant.turnLimit",
  assistant_thread_changed: "assistant.threadChanged",
};

function assistantErrorCode(error: unknown): string | undefined {
  const detail = error instanceof AssistantStreamError ? error.detail
    : isAxiosError<{ detail?: unknown }>(error) ? error.response?.data?.detail : undefined;
  if (typeof detail === "object" && detail !== null && "code" in detail && typeof detail.code === "string") {
    return detail.code;
  }
}

function requestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // randomUUID is unavailable on a plain HTTP network address.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function AssistantPage() {
  const { token } = useAuth();
  return <AssistantPageSession key={token} />;
}

function AssistantPageSession() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const config = useAssistantConfig();
  const threadId = params.get("thread") || null;
  const courseSlug = params.get("course_slug") ?? "";
  const lessonSlug = params.get("lesson_slug") ?? "";
  const lesson = !threadId && slugPattern.test(courseSlug) && slugPattern.test(lessonSlug)
    ? { course_slug: courseSlug, lesson_slug: lessonSlug }
    : undefined;

  return (
    <div className="assistant-page">
      {config.data?.enabled ? (
        <AssistantWorkspace
          threadId={threadId}
          lesson={lesson}
          webAvailable={config.data.web_search_available}
        />
      ) : (
        <>
          <h1 className="font-display text-3xl font-bold tracking-tight">{t("assistant.title")}</h1>
          <div className="mt-5 rounded-2xl border border-border bg-surface p-6">
            {config.isPending ? (
              <p role="status" className="flex items-center gap-2 text-sm text-muted"><Spinner /> {t("common.loading")}</p>
            ) : config.isError ? (
              <QueryError text={t("assistant.unavailable")} retry={() => void config.refetch()} />
            ) : (
              <p className="text-sm text-muted">{t("assistant.unavailable")}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function AssistantWorkspace({ threadId, lesson, webAvailable }: {
  threadId: string | null;
  lesson?: AssistantLesson;
  webAvailable: boolean;
}) {
  const { t } = useTranslation();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [draftRevision, setDraftRevision] = useState(0);
  const threads = useAssistantThreads();
  const conversationKey = threadId ? `thread:${threadId}` : `draft:${lesson?.course_slug}/${lesson?.lesson_slug}/${draftRevision}`;
  const newChat = (
    <Link
      to="/assistant"
      onClick={() => {
        setHistoryOpen(false);
        if (!threadId && !lesson) setDraftRevision((revision) => revision + 1);
      }}
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary-soft"
    >
      <IconPlus className="size-4 shrink-0" /> {t("assistant.newChat")}
    </Link>
  );

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 md:mb-5">
        <h1 className="font-display text-3xl font-bold tracking-tight">{t("assistant.title")}</h1>
        <div className="flex flex-wrap gap-2 md:hidden">
          <button
            type="button"
            className="inline-flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-muted hover:bg-surface hover:text-ink"
            aria-expanded={historyOpen}
            aria-controls="assistant-history"
            onClick={() => setHistoryOpen((open) => !open)}
          >
            <IconHistory className="size-4" /> {t("assistant.history")}
          </button>
          {newChat}
        </div>
      </div>
      <div className="assistant-workspace grid gap-3 md:grid-cols-[minmax(0,14rem)_minmax(0,1fr)] md:gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <aside
          aria-label={t("assistant.history")}
          id="assistant-history"
          className={`${historyOpen ? "flex" : "hidden"} min-w-0 flex-col overflow-hidden rounded-2xl border border-border bg-surface-2 p-3 md:flex`}
        >
          <div className="hidden flex-col md:flex">{newChat}</div>
          <p className="px-2 pt-1 pb-2 text-xs font-semibold text-muted md:pt-5">{t("assistant.history")}</p>
          <div className="min-h-0 overflow-y-auto max-md:max-h-48">
            {threads.isPending && <p role="status" className="px-2 py-2 text-sm text-muted">{t("common.loading")}</p>}
            {threads.isError && <QueryError text={t("assistant.historyError")} retry={() => void threads.refetch()} />}
            {threads.data?.length === 0 && <p className="px-2 py-2 text-sm text-muted">{t("assistant.noChats")}</p>}
            <ul className="space-y-0.5 px-1 py-1">
              {threads.data?.map((thread) => (
                <li key={thread.id} className="min-w-0">
                  <Link
                    to={threadLocation(thread.id)}
                    title={thread.title || t("assistant.newChat")}
                    aria-current={thread.id === threadId ? "page" : undefined}
                    onClick={() => setHistoryOpen(false)}
                    className="block truncate rounded-lg px-2.5 py-2.5 text-sm text-muted transition-colors hover:bg-surface hover:text-ink aria-[current=page]:bg-primary-soft aria-[current=page]:font-semibold aria-[current=page]:text-primary"
                  >
                    {thread.title || t("assistant.newChat")}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </aside>
        <Conversation key={conversationKey} threadId={threadId} initialLesson={lesson} webAvailable={webAvailable} />
      </div>
    </>
  );
}

function Conversation({ threadId, initialLesson, webAvailable }: {
  threadId: string | null;
  initialLesson?: AssistantLesson;
  webAvailable: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const thread = useAssistantThread(threadId);
  const progress = useProgress();
  const [draft, setDraft] = useState("");
  const [useWeb, setUseWeb] = useState(false);
  const [liveAnswer, setLiveAnswer] = useState<{ question: string; phase: AssistantPhase | null; text: string } | null>(null);
  const createdThread = useRef<string | null>(null);
  const lastTurn = useRef<AssistantTurn | null>(null);
  const activeStream = useRef<AbortController | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const timeline = useRef<HTMLDivElement>(null);
  const recentQuestion = useRef<HTMLDivElement>(null);
  const previousMessageCount = useRef<number | undefined>(undefined);
  const followStream = useRef(true);
  const wasStreaming = useRef(false);
  const selectedLesson = thread.data?.course_slug && thread.data.lesson_slug
    ? { course_slug: thread.data.course_slug, lesson_slug: thread.data.lesson_slug }
    : initialLesson;
  const lessonTitle = progress.data?.courses.find((course) => course.slug === selectedLesson?.course_slug)
    ?.lessons.find((lesson) => lesson.slug === selectedLesson?.lesson_slug)?.title;

  useLayoutEffect(() => () => activeStream.current?.abort(), []);

  const send = useMutation({
    mutationFn: async ({ turn, token, controller }: { turn: AssistantTurn; token: string; controller: AbortController }) => {
      const { signal } = controller;
      function checkSession() {
        signal.throwIfAborted();
        if (getToken() !== token) throw new Error("Authentication changed");
      }
      let id = threadId ?? createdThread.current;
      try {
        checkSession();
        if (!id) {
          const created = await createAssistantThread(token, initialLesson, signal);
          checkSession();
          id = created.id;
          createdThread.current = id;
        }
        const updated = await sendAssistantTurn(token, id, turn, signal, (update) => {
          if (getToken() !== token || signal.aborted) return;
          setLiveAnswer((current) => {
            if (!current) return current;
            if (update.type === "status") return { ...current, phase: update.phase };
            if (update.type === "reset") return { ...current, text: "" };
            return { ...current, text: current.text + update.text };
          });
        });
        checkSession();
        await queryClient.cancelQueries({ queryKey: assistantThreadKey(id), exact: true });
        checkSession();
        setLiveAnswer(null);
        queryClient.setQueryData(assistantThreadKey(id), updated);
        return updated;
      } catch (error) {
        if (id && getToken() === token && (signal.aborted || assistantErrorCode(error) === "assistant_thread_changed")) {
          void queryClient.invalidateQueries({ queryKey: assistantThreadKey(id), exact: true });
        }
        throw error;
      } finally {
        if (getToken() === token) void queryClient.invalidateQueries({ queryKey: assistantThreadsKey, exact: true });
      }
    },
    onSettled(_, error, { controller, token }) {
      if (activeStream.current === controller) activeStream.current = null;
      if (error && !controller.signal.aborted && getToken() === token) setLiveAnswer(null);
    },
  });

  const remove = useMutation({
    mutationFn: ({ id, token }: { id: string; token: string }) => {
      if (getToken() !== token) throw new Error("Authentication changed");
      return deleteAssistantThread(token, id);
    },
    onSuccess(_, { id, token }) {
      if (getToken() !== token) return;
      queryClient.removeQueries({ queryKey: assistantThreadKey(id), exact: true });
      void queryClient.invalidateQueries({ queryKey: assistantThreadsKey, exact: true });
    },
  });

  const messages = thread.data?.messages ?? [];
  const pendingText = liveAnswer?.question;
  const disabled = send.isPending || remove.isPending || (!!threadId && !thread.data);
  const errorCode = assistantErrorCode(send.error);
  const errorMessage = errorCode && Object.hasOwn(turnErrors, errorCode) ? turnErrors[errorCode] : "assistant.sendError";

  useLayoutEffect(() => {
    const viewport = timeline.current;
    const recent = recentQuestion.current;
    if (!viewport) return;
    if (pendingText || (wasStreaming.current && previousMessageCount.current !== messages.length)) {
      if (followStream.current) viewport.scrollTop = viewport.scrollHeight;
    } else if (recent && previousMessageCount.current === undefined) {
      viewport.scrollTop = Math.max(0, recent.offsetTop - 20);
    }
    if (recent || thread.data) previousMessageCount.current = messages.length;
    wasStreaming.current = !!pendingText;
  }, [messages.length, pendingText, liveAnswer?.phase, liveAnswer?.text, thread.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    const token = getToken();
    if (disabled || activeStream.current || !text || !token) return;
    const use_web = webAvailable && useWeb;
    const previous = lastTurn.current;
    const turn = previous?.text === text && previous.use_web === use_web
      ? previous
      : { text, use_web, request_id: requestId() };
    lastTurn.current = turn;
    const controller = new AbortController();
    activeStream.current = controller;
    followStream.current = true;
    setLiveAnswer({ question: turn.text, phase: null, text: "" });
    send.mutate({ turn, token, controller }, {
      onSuccess(updated) {
        if (controller.signal.aborted || getToken() !== token) return;
        lastTurn.current = null;
        setDraft("");
        setUseWeb(false);
        if (!threadId) navigate(threadLocation(updated.id), { replace: true });
      },
    });
  }

  function handleComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function removeThread() {
    const token = getToken();
    if (!threadId || !token || !window.confirm(t("assistant.deleteConfirm"))) return;
    remove.mutate({ id: threadId, token }, {
      onSuccess() {
        if (getToken() === token) navigate("/assistant", { replace: true });
      },
    });
  }

  function prefill(text: string) {
    setDraft(text);
    textarea.current?.focus();
  }

  return (
    <section
      aria-label={t("assistant.conversation")}
      className="assistant-conversation flex min-h-0 min-w-0 flex-col rounded-2xl border border-border bg-surface shadow-card"
    >
      {(thread.data || selectedLesson) && (
        <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border px-4 py-2 sm:px-6">
          <div className="min-w-0">
            {thread.data && <h2 className="truncate text-sm font-semibold" title={thread.data.title}>{thread.data.title || t("assistant.newChat")}</h2>}
            {selectedLesson && (
              <Link
                to={`/courses/${encodeURIComponent(selectedLesson.course_slug)}/lessons/${encodeURIComponent(selectedLesson.lesson_slug)}`}
                className="inline-flex max-w-full items-center gap-1.5 rounded text-xs font-semibold text-primary hover:underline"
              >
                <IconArticle className="size-4 shrink-0" />
                <span className="truncate">{lessonTitle || t("assistant.lessonContext", { lesson: selectedLesson.lesson_slug })}</span>
              </Link>
            )}
          </div>
          {thread.data && (
            <button
              type="button"
              aria-label={t("assistant.delete")}
              title={t("assistant.delete")}
              onClick={removeThread}
              disabled={disabled}
              className="flex size-10 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-danger-soft hover:text-danger disabled:opacity-45"
            >
              <IconTrash className="size-4" />
            </button>
          )}
        </div>
      )}

      <div
        ref={timeline}
        onScroll={(event) => {
          if (!liveAnswer) return;
          const viewport = event.currentTarget;
          followStream.current = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 32;
        }}
        tabIndex={0}
        role="log"
        aria-label={t("assistant.messages")}
        aria-relevant="additions"
        className="relative min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-4 sm:px-6"
      >
        <div className="mx-auto flex min-h-full max-w-2xl flex-col py-5 sm:py-6">
          {threadId && thread.isPending ? (
            <p role="status" className="m-auto flex items-center gap-2 text-sm text-muted"><Spinner /> {t("common.loading")}</p>
          ) : threadId && thread.isError && !thread.data ? (
            <div className="m-auto"><QueryError text={t("assistant.threadError")} retry={() => void thread.refetch()} /></div>
          ) : messages.length === 0 && !pendingText ? (
            <div className="my-auto py-3 sm:py-6">
              <span className="inline-flex size-12 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                <IconSparkles className="size-6" />
              </span>
              <h2 className="mt-4 font-display text-2xl font-bold tracking-tight sm:text-3xl">
                {t(selectedLesson ? "assistant.lessonHeading" : "assistant.startHeading")}
              </h2>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
                {t(selectedLesson ? "assistant.lessonHint" : "assistant.startHint")}
              </p>
              <div className="mt-5 grid gap-2 sm:grid-cols-2">
                {[IconArticle, IconTarget].map((Icon, index) => {
                  const prompt = t(selectedLesson
                    ? (index === 0 ? "assistant.lessonPrompt" : "assistant.interviewPrompt")
                    : (index === 0 ? "assistant.examplePrompt" : "assistant.reviewPrompt"));
                  return (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => prefill(prompt)}
                      className="flex min-h-12 items-center gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2 text-left text-sm font-medium transition-colors hover:bg-primary-soft hover:text-primary"
                    >
                      <Icon className="size-4 shrink-0 text-primary" /> {prompt}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => (
                message.role === "assistant" ? <AssistantAnswer key={message.id} message={message} /> : (
                  <div
                    key={message.id}
                    ref={!pendingText && index >= messages.length - 2 ? recentQuestion : undefined}
                    className="flex justify-end"
                  >
                    <UserMessage text={message.text} />
                  </div>
                )
              ))}
              {liveAnswer && (
                <>
                  <div ref={recentQuestion} className="flex justify-end"><UserMessage text={liveAnswer.question} /></div>
                  <div className="flex min-w-0 gap-3">
                    <span aria-hidden className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                      <IconSparkles className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="mb-2 text-sm font-semibold">{t("assistant.title")}</p>
                      <p role="status" className="flex items-center gap-2 text-sm font-medium text-muted">
                        <Spinner className="shrink-0 text-primary motion-reduce:animate-none" />
                        {t(liveAnswer.phase ? `assistant.phase.${liveAnswer.phase}` : "assistant.pending")}
                      </p>
                      {liveAnswer.text && (
                        <div aria-live="off" className="assistant-answer-text mt-2 whitespace-pre-wrap">{liveAnswer.text}</div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <form onSubmit={submit} className="border-t border-border px-4 pt-3 pb-4 sm:px-6">
        <div className="mx-auto max-w-2xl">
          {send.isError && (
            <p role="alert" className="mb-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {t(errorMessage)}
            </p>
          )}
          {remove.isError && <p role="alert" className="mb-2 text-sm text-danger">{t("assistant.deleteError")}</p>}
          <div className="rounded-xl border border-border bg-surface-2 focus-within:border-primary/50">
            <label className="sr-only" htmlFor="assistant-composer">{t("assistant.composer")}</label>
            <textarea
              id="assistant-composer"
              ref={textarea}
              value={send.isPending ? "" : draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKey}
              disabled={remove.isPending || (!!threadId && !thread.data)}
              readOnly={send.isPending}
              placeholder={t(messages.length ? "assistant.followup" : "assistant.placeholder")}
              rows={2}
              maxLength={MAX_MESSAGE_LENGTH}
              className="block max-h-44 min-h-14 w-full resize-y bg-transparent px-3 pt-2.5 text-base leading-relaxed placeholder:text-muted focus-visible:outline-none"
            />
            <div className="flex min-h-12 flex-wrap items-center justify-end gap-2 px-2 pb-2">
              {webAvailable && (
                <label
                  className="mr-auto inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg px-2 text-xs font-semibold text-muted hover:bg-primary-soft has-checked:bg-primary-soft has-checked:text-primary"
                >
                  <input
                    type="checkbox"
                    checked={useWeb}
                    onChange={(event) => setUseWeb(event.target.checked)}
                    disabled={disabled}
                    className="size-4 accent-primary"
                    aria-describedby="assistant-web-hint"
                  />
                  <IconGlobe className="size-3.5" /> {t("assistant.web")}
                </label>
              )}
              <Button type="submit" disabled={disabled || !draft.trim()} aria-keyshortcuts="Control+Enter Meta+Enter" className="min-h-10">
                {t(send.isError ? "assistant.retry" : "assistant.send")} <IconArrowUp className="size-4" />
              </Button>
            </div>
          </div>
          {webAvailable && (
            <p id="assistant-web-hint" className={`${useWeb ? "mt-2" : "sr-only"} text-xs leading-relaxed text-muted`}>
              {t("assistant.webHint")}
            </p>
          )}
        </div>
      </form>
    </section>
  );
}

function QueryError({ text, retry }: { text: string; retry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-1">
      <p role="alert" className="text-sm text-danger">{text}</p>
      <Button variant="ghost" type="button" onClick={retry}>{t("assistant.retry")}</Button>
    </div>
  );
}

function UserMessage({ text }: { text: string }) {
  const { t } = useTranslation();
  return (
    <div className="max-w-[88%] rounded-2xl rounded-br-md bg-primary-soft px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">
      <span className="sr-only">{t("assistant.you")} </span>{text}
    </div>
  );
}
