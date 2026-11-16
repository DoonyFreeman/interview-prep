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
  sendAssistantTurn,
  useAssistantConfig,
  useAssistantThread,
  useAssistantThreads,
  type AssistantThreadSummary,
  type AssistantLesson,
  type AssistantPhase,
  type AssistantTurn,
} from "../api/assistant";
import { useProgress } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { AssistantAnswer } from "../components/AssistantAnswer";
import { AssistantHistory, assistantThreadLocation, type AssistantThreadAction } from "../components/AssistantHistory";
import { AssistantThreadDialog } from "../components/AssistantThreadDialog";
import { LanguageToggle } from "../components/LanguageToggle";
import { ThemeToggle } from "../components/ThemeToggle";
import { Button } from "../components/Button";
import {
  IconArrowUp,
  IconArticle,
  IconGlobe,
  IconPencil,
  IconSidebar,
  IconSparkles,
  IconTarget,
  IconTrash,
} from "../components/icons";
import { Spinner } from "../components/Spinner";
import { getToken } from "../lib/token";
import "./assistant.css";

const slugPattern = /^[a-z0-9_-]+$/;
const MAX_MESSAGE_LENGTH = 3000;
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
        <main className="mx-auto max-w-xl p-6 sm:p-12">
          <Link to="/" className="mb-6 inline-block text-sm font-semibold text-primary hover:underline">{t("assistant.back")}</Link>
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
        </main>
      )}
    </div>
  );
}

type ConversationView = { key: string; threadId: string | null; lesson?: AssistantLesson };
type ChatDraft = { text: string; web: boolean; request: AssistantTurn | null };
type Answering = { view: ConversationView; id: string | null };

function AssistantWorkspace({ threadId, lesson, webAvailable }: {
  threadId: string | null;
  lesson?: AssistantLesson;
  webAvailable: boolean;
}) {
  const navigate = useNavigate();
  const [draftRevision, setDraftRevision] = useState(0);
  const [answering, setAnswering] = useState<Answering | null>(null);
  const [action, setAction] = useState<AssistantThreadAction | null>(null);
  const drafts = useRef(new Map<string, ChatDraft>());
  const threadKeys = useRef(new Map<string, string>());
  const scrollPositions = useRef(new Map<string, number>());
  const drawer = useRef<HTMLDialogElement>(null);
  const threads = useAssistantThreads();
  const view: ConversationView = {
    key: threadId
      ? threadKeys.current.get(threadId) ?? `thread:${threadId}`
      : `draft:${lesson?.course_slug}/${lesson?.lesson_slug}/${draftRevision}`,
    threadId, lesson,
  };
  const current = useRef(view);
  useLayoutEffect(() => { current.current = view; });
  const views = answering && answering.view.key !== view.key ? [view, answering.view] : [view];

  function openAction(nextAction: AssistantThreadAction) {
    if (nextAction.thread.id !== answering?.id) setAction(nextAction);
  }

  return (
    <div className="assistant-workspace">
      <AssistantHistory
        threadId={threadId}
        answeringId={answering?.id ?? null}
        drawer={drawer}
        onAction={openAction}
        onNew={() => {
          drawer.current?.close();
          if (!threadId && !lesson && answering?.view.key !== view.key) drafts.current.delete(view.key);
          setDraftRevision((revision) => revision + 1);
        }}
      />
      <main className="assistant-main">
        {views.map((item) => {
          const id = item.threadId ?? (answering?.view.key === item.key ? answering.id : null);
          const summary = threads.data?.find((thread) => thread.id === id);
          return (
            <div className="assistant-view" key={item.key} hidden={item.key !== view.key}>
              <Conversation
                view={item}
                summary={summary}
                active={item.key === view.key}
                webAvailable={webAvailable}
                busyElsewhere={!!answering && answering.view.key !== item.key}
                drafts={drafts.current}
                scrollPositions={scrollPositions.current}
                onHistory={() => drawer.current?.showModal()}
                onAction={openAction}
                onAnswering={(id) => setAnswering({ view: item, id })}
                onCreated={(id) => {
                  threadKeys.current.set(id, item.key);
                  setAnswering({ view: { ...item, threadId: id }, id });
                  if (current.current.key === item.key) {
                    navigate(assistantThreadLocation(id), { replace: true });
                  }
                  if (current.current.threadId || current.current.key === item.key) {
                    setDraftRevision((revision) => revision + 1);
                  }
                }}
                onSettled={() => setAnswering((pending) => pending?.view.key === item.key ? null : pending)}
              />
            </div>
          );
        })}
      </main>
      {action && (
        <AssistantThreadDialog
          action={action}
          onDismiss={() => setAction(null)}
          onDeleted={(id) => {
            const key = threadKeys.current.get(id) ?? `thread:${id}`;
            threadKeys.current.delete(id);
            drafts.current.delete(key);
            scrollPositions.current.delete(key);
            if (current.current.threadId === id) navigate("/assistant", { replace: true });
          }}
        />
      )}
    </div>
  );
}

function Conversation({
  view, summary, active, webAvailable, busyElsewhere, drafts, scrollPositions,
  onHistory, onAction, onAnswering, onCreated, onSettled,
}: {
  view: ConversationView;
  summary?: AssistantThreadSummary;
  active: boolean;
  webAvailable: boolean;
  busyElsewhere: boolean;
  drafts: Map<string, ChatDraft>;
  scrollPositions: Map<string, number>;
  onHistory: () => void;
  onAction: (action: AssistantThreadAction) => void;
  onAnswering: (id: string | null) => void;
  onCreated: (id: string) => void;
  onSettled: () => void;
}) {
  const { key, threadId, lesson: initialLesson } = view;
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const thread = useAssistantThread(threadId);
  const progress = useProgress();
  const [draft, setDraft] = useState(() => drafts.get(key)?.text ?? "");
  const [useWeb, setUseWeb] = useState(() => drafts.get(key)?.web ?? false);
  const [liveAnswer, setLiveAnswer] = useState<{ question: string; phase: AssistantPhase | null; text: string } | null>(null);
  const lastTurn = useRef(drafts.get(key)?.request ?? null);
  const activeStream = useRef<AbortController | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const timeline = useRef<HTMLDivElement>(null);
  const previousMessageCount = useRef<number | undefined>(undefined);
  const followStream = useRef(true);
  const wasStreaming = useRef(false);
  const selectedLesson = thread.data?.course_slug && thread.data.lesson_slug
    ? { course_slug: thread.data.course_slug, lesson_slug: thread.data.lesson_slug }
    : initialLesson;
  const lessonTitle = progress.data?.courses.find((course) => course.slug === selectedLesson?.course_slug)
    ?.lessons.find((lesson) => lesson.slug === selectedLesson?.lesson_slug)?.title;

  useLayoutEffect(() => () => activeStream.current?.abort(), []);
  useLayoutEffect(() => {
    if (draft.trim()) drafts.set(key, { text: draft, web: useWeb, request: lastTurn.current });
    else drafts.delete(key);
  }, [draft, useWeb, key, drafts]);

  const send = useMutation({
    mutationFn: async ({ turn, token, controller }: { turn: AssistantTurn; token: string; controller: AbortController }) => {
      const { signal } = controller;
      function checkSession() {
        signal.throwIfAborted();
        if (getToken() !== token) throw new Error("Authentication changed");
      }
      let id = threadId;
      try {
        checkSession();
        if (!id) {
          const created = await createAssistantThread(token, initialLesson, signal);
          checkSession();
          id = created.id;
          queryClient.setQueryData(assistantThreadKey(id), created);
          onCreated(id);
          void queryClient.invalidateQueries({ queryKey: assistantThreadsKey, exact: true });
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
    onSuccess(_, { token }) {
      if (getToken() !== token) return;
      lastTurn.current = null;
      setDraft("");
      setUseWeb(false);
      drafts.delete(key);
    },
    onSettled(_, error, { controller, token }) {
      if (activeStream.current === controller) activeStream.current = null;
      if (getToken() !== token) return;
      if (error) setLiveAnswer(null);
      onSettled();
    },
  });

  const messages = thread.data?.messages ?? [];
  const pendingText = liveAnswer?.question;
  const loadingThread = !!threadId && !thread.data;
  const disabled = send.isPending || busyElsewhere || loadingThread;
  const failed = send.isError && !send.variables?.controller.signal.aborted;
  const displayThread = thread.data ?? summary;
  const errorCode = assistantErrorCode(send.error);
  const errorMessage = errorCode && Object.hasOwn(turnErrors, errorCode) ? turnErrors[errorCode] : "assistant.sendError";

  useLayoutEffect(() => {
    const viewport = timeline.current;
    if (!active || !viewport) return;
    if (pendingText || (wasStreaming.current && previousMessageCount.current !== messages.length)) {
      if (followStream.current) viewport.scrollTop = viewport.scrollHeight;
    } else if (thread.data && previousMessageCount.current === undefined) {
      const saved = scrollPositions.get(key);
      viewport.scrollTop = saved === undefined || saved === Infinity ? viewport.scrollHeight : saved;
    }
    if (thread.data || pendingText) previousMessageCount.current = messages.length;
    wasStreaming.current = !!pendingText;
  }, [active, key, messages.length, pendingText, liveAnswer?.phase, liveAnswer?.text, thread.data, scrollPositions]);

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
    drafts.set(key, { text: turn.text, web: turn.use_web, request: turn });
    onAnswering(threadId);
    send.mutate({ turn, token, controller });
  }

  function handleComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function prefill(text: string) {
    setDraft(text);
    textarea.current?.focus();
  }

  return (
    <section aria-label={t("assistant.conversation")} className="assistant-conversation">
      <header className="assistant-chat-header">
        <button className="assistant-icon-button assistant-open-history" type="button" aria-label={t("assistant.history")} aria-haspopup="dialog" aria-controls="assistant-mobile-history" onClick={onHistory}>
          <IconSidebar className="size-5" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-lg font-bold tracking-tight" title={displayThread?.title}>{displayThread?.title || t("assistant.title")}</h1>
          {selectedLesson && (
            <Link
              to={`/courses/${encodeURIComponent(selectedLesson.course_slug)}/lessons/${encodeURIComponent(selectedLesson.lesson_slug)}`}
              className="inline-flex max-w-full items-center gap-1.5 rounded text-xs font-semibold text-primary hover:underline"
            >
              <IconArticle className="size-3.5 shrink-0" />
              <span className="truncate">{lessonTitle || t("assistant.lessonContext", { lesson: selectedLesson.lesson_slug })}</span>
            </Link>
          )}
        </div>
        {displayThread && (
          <div className="flex shrink-0 items-center gap-0.5">
            <button type="button" className="assistant-icon-button" aria-label={t("assistant.rename")} title={t("assistant.rename")} disabled={send.isPending} onClick={() => onAction({ kind: "rename", thread: displayThread })}>
              <IconPencil className="size-4" />
            </button>
            <button type="button" className="assistant-icon-button assistant-delete-action" aria-label={t("assistant.delete")} title={t("assistant.delete")} disabled={send.isPending} onClick={() => onAction({ kind: "delete", thread: displayThread })}>
              <IconTrash className="size-4" />
            </button>
          </div>
        )}
        <div className="assistant-chat-preferences">
          <ThemeToggle />
          <span className="hidden sm:inline-flex"><LanguageToggle /></span>
        </div>
      </header>

      <div
        ref={timeline}
        onScroll={(event) => {
          if (!active) return;
          const viewport = event.currentTarget;
          followStream.current = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 32;
          scrollPositions.set(key, followStream.current ? Infinity : viewport.scrollTop);
        }}
        tabIndex={0}
        role="log"
        aria-label={t("assistant.messages")}
        aria-relevant="additions"
        className="assistant-timeline"
      >
        <div className="assistant-reading-column">
          {threadId && thread.isPending ? (
            <div role="status" className="assistant-thread-loading">
              <span className="sr-only">{t("common.loading")}</span>
              <div /><div /><div />
            </div>
          ) : threadId && thread.isError && !thread.data ? (
            <div className="m-auto"><QueryError text={t("assistant.threadError")} retry={() => void thread.refetch()} /></div>
          ) : messages.length === 0 && !pendingText ? (
            <div className="assistant-welcome">
              <span className="assistant-welcome-icon">
                <IconSparkles className="size-6" />
              </span>
              <h2 className="assistant-welcome-title">
                {t(selectedLesson ? "assistant.lessonHeading" : "assistant.startHeading")}
              </h2>
              <p className="mt-3 max-w-md text-pretty text-sm leading-relaxed text-muted sm:text-base">
                {t(selectedLesson ? "assistant.lessonHint" : "assistant.startHint")}
              </p>
              <div className="assistant-prompts">
                {[IconArticle, IconTarget].map((Icon, index) => {
                  const prompt = t(selectedLesson
                    ? (index === 0 ? "assistant.lessonPrompt" : "assistant.interviewPrompt")
                    : (index === 0 ? "assistant.examplePrompt" : "assistant.reviewPrompt"));
                  return (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => prefill(prompt)}
                      className="assistant-prompt"
                    >
                      <Icon className="size-4 shrink-0 text-primary" /> {prompt}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="assistant-transcript space-y-6">
              {messages.map((message) => (
                message.role === "assistant" ? <AssistantAnswer key={message.id} message={message} /> : (
                  <div
                    key={message.id}
                    className="flex justify-end"
                  >
                    <UserMessage text={message.text} />
                  </div>
                )
              ))}
              {liveAnswer && (
                <>
                  <div className="flex justify-end"><UserMessage text={liveAnswer.question} /></div>
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

      <form onSubmit={submit} className="assistant-compose-area">
        <div className="assistant-compose-width">
          {failed && (
            <p role="alert" className="mb-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {t(errorMessage)}
            </p>
          )}
          <div className="assistant-compose-box">
            <label className="sr-only" htmlFor={`assistant-composer-${key}`}>{t("assistant.composer")}</label>
            <textarea
              id={`assistant-composer-${key}`}
              ref={textarea}
              value={send.isPending ? "" : draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKey}
              disabled={loadingThread}
              readOnly={send.isPending}
              placeholder={t(messages.length ? "assistant.followup" : "assistant.placeholder")}
              rows={1}
              maxLength={MAX_MESSAGE_LENGTH}
              className="assistant-compose-input block w-full bg-transparent px-3 pt-2.5 text-base leading-relaxed placeholder:text-muted focus-visible:outline-none"
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
                    aria-describedby={`assistant-web-hint-${key}`}
                  />
                  <IconGlobe className="size-3.5" /> {t("assistant.web")}
                </label>
              )}
              {busyElsewhere && <span role="status" className="text-xs text-muted">{t("assistant.answering")}</span>}
              {send.isPending ? (
                <Button type="button" variant="secondary" onClick={() => activeStream.current?.abort()}>
                  <span aria-hidden className="size-2.5 rounded-xs bg-current" /> {t("assistant.stop")}
                </Button>
              ) : (
                <Button type="submit" disabled={disabled || !draft.trim()} aria-keyshortcuts="Control+Enter Meta+Enter" className="min-h-10">
                  {t(failed ? "assistant.retry" : "assistant.send")} <IconArrowUp className="size-4" />
                </Button>
              )}
            </div>
          </div>
          {webAvailable && (
            <p id={`assistant-web-hint-${key}`} className={`${useWeb ? "mt-2" : "sr-only"} text-xs leading-relaxed text-muted`}>
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
