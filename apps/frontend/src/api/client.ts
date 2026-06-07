// API client: base URL, error normalization, and the SSE helper for /api/chat.
// The chat stream uses fetch + ReadableStream (not EventSource) because the
// request needs a POST body (docs/components/06 §2).

import type {
  AdminConversationList,
  ConversationCreated,
  ConversationDetail,
  Metrics,
  RefundList,
  Selection,
  SSEEvent,
  TraceResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body?.error;
    if (e?.code) return new ApiError(e.code, e.message ?? "Request failed");
  } catch {
    /* fall through */
  }
  return new ApiError("http_error", `Request failed (${res.status})`);
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export function createConversation(): Promise<ConversationCreated> {
  return fetch(`${BASE}/conversations`, { method: "POST" }).then(async (res) => {
    if (!res.ok) throw await toError(res);
    return (await res.json()) as ConversationCreated;
  });
}

export const getConversation = (id: string) =>
  getJSON<ConversationDetail>(`/conversations/${id}`);

export const getAdminConversations = (status?: string) =>
  getJSON<AdminConversationList>(
    `/admin/conversations${status ? `?status=${encodeURIComponent(status)}` : ""}`,
  );

export const getTrace = (id: string) =>
  getJSON<TraceResponse>(`/admin/conversations/${id}/trace`);

export const getRefunds = (status?: string) =>
  getJSON<RefundList>(`/admin/refunds${status ? `?status=${encodeURIComponent(status)}` : ""}`);

export const getMetrics = () => getJSON<Metrics>("/admin/metrics");

export interface ChatBody {
  conversation_id: string;
  message: string;
  selection?: Selection[];
}

export function parseFrame(frame: string): SSEEvent | null {
  let type: string | null = null;
  let data: string | null = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7).trim();
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!type) return null;
  return { type, data: data ? JSON.parse(data) : {} } as SSEEvent;
}

export async function* streamChat(
  body: ChatBody,
  sessionToken: string,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${sessionToken}`,
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw await toError(res);
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const ev = parseFrame(frame);
      if (ev) yield ev;
    }
  }
}
