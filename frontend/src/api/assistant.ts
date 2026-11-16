import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { clearToken, getToken } from "../lib/token";

interface AssistantConfig {
  enabled: boolean;
  web_search_available: boolean;
}

export interface AssistantLesson {
  course_slug: string;
  lesson_slug: string;
}

export interface AssistantSource {
  title: string;
  url: string;
  kind: "lesson" | "web";
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources: AssistantSource[];
  tool_activity?: ("search_lessons" | "read_lesson_section" | "get_review_queue" | "web_search")[];
  created_at: string;
}

export interface AssistantThreadSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface AssistantThread extends AssistantThreadSummary {
  course_slug: string | null;
  lesson_slug: string | null;
  messages: AssistantMessage[];
}

export interface AssistantTurn {
  text: string;
  use_web: boolean;
  request_id: string;
}

const assistantPhases = [
  "thinking", "search_lessons", "read_lesson_section", "get_review_queue", "web_search", "generating", "saving",
] as const;

export type AssistantPhase = typeof assistantPhases[number];

export type AssistantStreamUpdate =
  | { type: "status"; phase: AssistantPhase }
  | { type: "delta"; text: string }
  | { type: "reset" };

export class AssistantStreamError extends Error {
  constructor(public status: number, public detail: unknown) {
    super("Assistant request failed");
  }
}

export const assistantThreadsKey = ["assistant", "threads"] as const;
export const assistantThreadKey = (id: string | null) => [...assistantThreadsKey, id] as const;

const threadUrl = (id: string) => `/assistant/threads/${encodeURIComponent(id)}`;

export function useAssistantConfig() {
  return useQuery({
    queryKey: ["assistant", "config"],
    queryFn: async ({ signal }) =>
      (await api.get<AssistantConfig>("/assistant/config", { signal })).data,
  });
}

export function useAssistantThreads() {
  return useQuery({
    queryKey: assistantThreadsKey,
    queryFn: async ({ signal }) =>
      (await api.get<{ threads: AssistantThreadSummary[] }>("/assistant/threads", { signal })).data.threads,
  });
}

export function useAssistantThread(id: string | null) {
  return useQuery({
    queryKey: assistantThreadKey(id),
    enabled: !!id,
    queryFn: async ({ signal }) => (await api.get<AssistantThread>(threadUrl(id!), { signal })).data,
  });
}

export async function createAssistantThread(token: string, lesson?: AssistantLesson, signal?: AbortSignal) {
  return (await api.post<AssistantThread>("/assistant/threads", lesson ?? {}, {
    signal,
    headers: { Authorization: `Bearer ${token}` },
  })).data;
}

export async function sendAssistantTurn(
  token: string,
  id: string,
  turn: AssistantTurn,
  signal: AbortSignal,
  onUpdate: (update: AssistantStreamUpdate) => void,
): Promise<AssistantThread> {
  function requestError(status: number, detail: unknown) {
    signal.throwIfAborted();
    if (status === 401 && getToken() === token) {
      clearToken();
      if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
    }
    return new AssistantStreamError(status, detail);
  }

  const response = await fetch(api.getUri({ url: `${threadUrl(id)}/messages/stream` }), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(turn),
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => undefined);
    throw requestError(response.status, payload?.detail);
  }
  if (!response.body || !response.headers.get("Content-Type")?.toLowerCase().startsWith("text/event-stream")) {
    throw new Error("Expected an assistant event stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  let data: string[] = [];
  try {
    while (true) {
      const { value, done } = await reader.read();
      signal.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });

      let lineEnd: number;
      while ((lineEnd = buffer.search(/[\r\n]/)) !== -1) {
        const carriageReturn = buffer[lineEnd] === "\r";
        // A CRLF pair can straddle network chunks.
        if (carriageReturn && lineEnd === buffer.length - 1 && !done) break;
        const line = buffer.slice(0, lineEnd);
        buffer = buffer.slice(lineEnd + (carriageReturn && buffer[lineEnd + 1] === "\n" ? 2 : 1));
        if (line) {
          const colon = line.indexOf(":");
          const field = colon === -1 ? line : line.slice(0, colon);
          const fieldValue = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
          if (field === "event") event = fieldValue;
          if (field === "data") data.push(fieldValue);
          continue;
        }

        signal.throwIfAborted();
        if (data.length > 0) {
          switch (event) {
            case "status": {
              const { phase } = JSON.parse(data.join("\n"));
              if (assistantPhases.includes(phase)) onUpdate({ type: "status", phase });
              break;
            }
            case "delta": {
              const { text } = JSON.parse(data.join("\n"));
              if (typeof text === "string") onUpdate({ type: "delta", text });
              break;
            }
            case "reset":
              onUpdate({ type: "reset" });
              break;
            case "error": {
              const { status, detail } = JSON.parse(data.join("\n"));
              throw requestError(status, detail);
            }
            case "done": {
              const thread: AssistantThread = JSON.parse(data.join("\n"));
              if (typeof thread?.id !== "string" || !Array.isArray(thread.messages)) {
                throw new Error("Invalid assistant thread");
              }
              return thread;
            }
          }
        }
        event = "";
        data = [];
      }
      if (done) throw new Error("Assistant stream ended before the reply was saved");
    }
  } finally {
    void reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export async function deleteAssistantThread(token: string, id: string) {
  await api.delete(threadUrl(id), { headers: { Authorization: `Bearer ${token}` } });
}
