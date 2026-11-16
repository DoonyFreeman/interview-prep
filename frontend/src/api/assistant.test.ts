import { afterEach, expect, it, vi } from "vitest";
import { AssistantStreamError, sendAssistantTurn } from "./assistant";

const turn = { text: "Explain async", use_web: false, request_id: "same-request-id" };
const thread = {
  id: "thread-id",
  title: turn.text,
  course_slug: null,
  lesson_slug: null,
  updated_at: "2026-11-15T00:00:00Z",
  messages: [{
    id: "saved-answer",
    role: "assistant",
    text: "Final answer",
    sources: [{ title: "Async fundamentals", url: "/courses/python/lessons/async", kind: "lesson" }],
    created_at: "2026-11-15T00:00:00Z",
  }],
};

function stream(content: string): Response {
  const bytes = new TextEncoder().encode(content);
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      // Split UTF-8 characters, CRLF and SSE fields at arbitrary network boundaries.
      for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
      controller.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}

afterEach(() => vi.unstubAllGlobals());

it("emits phases, UTF-8 text and resets before returning the saved thread", async () => {
  const response = stream([
    ": heartbeat\r\n\r\n",
    'event: status\r\ndata: {"phase":"search_lessons"}\r\n\r\n',
    'event: delta\r\ndata: {"text":\r\ndata: "Черновик 🐈"}\r\n\r\n',
    'event: reset\rdata: {}\r\r',
    'event: status\ndata: {"phase":"generating"}\n\n',
    'event: delta\ndata: {"text":"Новый ответ"}\n\n',
    'event: status\ndata: {"phase":"saving"}\n\n',
    `event: done\ndata: ${JSON.stringify(thread)}\n\n`,
  ].join(""));
  const fetch = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetch);
  const controller = new AbortController();
  const onUpdate = vi.fn();

  await expect(sendAssistantTurn("token", thread.id, turn, controller.signal, onUpdate)).resolves.toEqual(thread);
  expect(onUpdate.mock.calls.flat()).toEqual([
    { type: "status", phase: "search_lessons" },
    { type: "delta", text: "Черновик 🐈" },
    { type: "reset" },
    { type: "status", phase: "generating" },
    { type: "delta", text: "Новый ответ" },
    { type: "status", phase: "saving" },
  ]);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining(`/api/assistant/threads/${thread.id}/messages/stream`), {
    method: "POST",
    headers: { Authorization: "Bearer token", "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(turn),
    signal: controller.signal,
  });
});

it("requires a complete done event after partial text", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream(
    `event: delta\ndata: {"text":"partial"}\n\nevent: done\ndata: ${JSON.stringify(thread)}\n`,
  )));
  const onUpdate = vi.fn();

  await expect(sendAssistantTurn("token", thread.id, turn, new AbortController().signal, onUpdate))
    .rejects.toThrow("Assistant stream ended before the reply was saved");
  expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ type: "delta", text: "partial" });
});

it("stops emitting updates on cancellation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream(
    'event: status\ndata: {"phase":"thinking"}\n\nevent: delta\ndata: {"text":"partial"}\n\n',
  )));
  const controller = new AbortController();
  const onUpdate = vi.fn(() => controller.abort());

  await expect(sendAssistantTurn("token", thread.id, turn, controller.signal, onUpdate)).rejects.toMatchObject({ name: "AbortError" });
  expect(onUpdate).toHaveBeenCalledExactlyOnceWith({ type: "status", phase: "thinking" });
});

it("keeps HTTP and streamed error details available for retry messages", async () => {
  const detail = { code: "assistant_busy", message: "Please try again" };
  const responses = [
    new Response(JSON.stringify({ detail }), { status: 409 }),
    stream(`event: error\ndata: ${JSON.stringify({ status: 409, detail })}\n\n`),
  ];

  for (const response of responses) {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(sendAssistantTurn("token", thread.id, turn, new AbortController().signal, vi.fn()))
      .rejects.toMatchObject({ status: 409, detail });
  }
});

it.each(["old-token", "new-token"])("only clears a matching token on 401 with %s", async (currentToken) => {
  const removeItem = vi.fn();
  const location = { pathname: "/assistant", href: "/assistant" };
  vi.stubGlobal("localStorage", { getItem: () => currentToken, removeItem });
  vi.stubGlobal("window", { location });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

  await expect(sendAssistantTurn("old-token", thread.id, turn, new AbortController().signal, vi.fn()))
    .rejects.toBeInstanceOf(AssistantStreamError);
  expect(removeItem).toHaveBeenCalledTimes(currentToken === "old-token" ? 1 : 0);
  expect(location.href).toBe(currentToken === "old-token" ? "/login" : "/assistant");
});
