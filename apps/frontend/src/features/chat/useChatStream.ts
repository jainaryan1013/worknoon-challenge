// The streaming brain (docs/components/06 §3.1-3.2): send a turn, consume the
// SSE stream, append tokens, surface tool status, render a ReturnSelector,
// flip decision badges, end on done, show a message on error.

import { useCallback, useRef, useState } from "react";

import {
  ChatBody,
  createConversation as defaultCreateConversation,
  streamChat as defaultStreamChat,
} from "../../api/client";
import type { DecisionPayload, ReturnSelectorPayload, Selection, SSEEvent } from "../../api/types";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
}

export interface SelectorState {
  payload: ReturnSelectorPayload;
  locked: boolean;
}

export interface ChatStreamDeps {
  stream?: (body: ChatBody, signal?: AbortSignal) => AsyncGenerator<SSEEvent>;
  createConv?: () => Promise<{ conversation_id: string }>;
}

export function useChatStream(deps: ChatStreamDeps = {}) {
  const stream = deps.stream ?? defaultStreamChat;
  const createConv = deps.createConv ?? defaultCreateConversation;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<DecisionPayload[]>([]);
  const [selector, setSelector] = useState<SelectorState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const convIdRef = useRef<string | null>(null);
  const streamingRef = useRef(false);
  const idRef = useRef(0);
  const nextId = () => (idRef.current += 1);

  const appendToLastAssistant = (delta: string) => {
    setMessages((prev) => {
      const copy = [...prev];
      for (let i = copy.length - 1; i >= 0; i--) {
        if (copy[i].role === "assistant") {
          copy[i] = { ...copy[i], text: copy[i].text + delta };
          break;
        }
      }
      return copy;
    });
  };

  const handle = (ev: SSEEvent) => {
    switch (ev.type) {
      case "token":
        appendToLastAssistant(ev.data.text);
        break;
      case "tool_call":
        setToolStatus(ev.data.summary);
        break;
      case "tool_result":
        setToolStatus(null);
        break;
      case "return_selector":
        setSelector({ payload: ev.data, locked: false });
        break;
      case "decision":
        setDecisions((prev) => [...prev, ev.data]);
        break;
      case "error":
        setError(ev.data.message);
        break;
      case "done":
        break;
    }
  };

  const send = useCallback(
    async (text: string, selection?: Selection[]) => {
      if (streamingRef.current || !text.trim()) return;
      setError(null);

      let convId = convIdRef.current;
      if (!convId) {
        const created = await createConv();
        convId = created.conversation_id;
        convIdRef.current = convId;
        setConversationId(convId);
      }

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", text },
        { id: nextId(), role: "assistant", text: "" },
      ]);
      setStreaming(true);
      streamingRef.current = true;
      setToolStatus(null);

      try {
        for await (const ev of stream({ conversation_id: convId, message: text, selection })) {
          handle(ev);
        }
      } catch {
        setError("Something went wrong. Please try again.");
      } finally {
        setStreaming(false);
        streamingRef.current = false;
        setToolStatus(null);
      }
    },
    [stream, createConv],
  );

  const confirmSelection = useCallback(
    (selection: Selection[], message: string) => {
      setSelector((prev) => (prev ? { ...prev, locked: true } : prev));
      void send(message, selection);
    },
    [send],
  );

  return {
    messages,
    streaming,
    toolStatus,
    decisions,
    selector,
    error,
    conversationId,
    send,
    confirmSelection,
  };
}
