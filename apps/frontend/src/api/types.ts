// Shared API types.
//
// REST request/response types are sourced from the generated OpenAPI client
// (./generated/schema.ts, regenerated via `make gen-client`) so they can never
// silently drift from the backend Pydantic models. We re-export them under the
// names the app uses (a few differ from the backend class names, noted below).
//
// The SSE event union is hand-written (it mirrors app/agent/events.py) because
// OpenAPI can't describe an event stream (docs/components/06 §2-3). The selector
// and decision payloads it carries are likewise stream-only — they are not REST
// response bodies, so they have no schema component to alias.

import type { components } from "./generated/schema";

type Schemas = components["schemas"];

// --- REST types (aliased to the generated schema) ---

export type ConversationCreated = Schemas["ConversationCreated"];
export type MessageOut = Schemas["MessageOut"];
export type ConversationDetail = Schemas["ConversationDetail"];

// Backend class names differ from the app's UI-facing names; alias to bridge.
export type AdminConversationItem = Schemas["ConversationListItem"];
export type AdminConversationList = Schemas["ConversationList"];
export type RefundItem = Schemas["RefundOut"];
export type RefundList = Schemas["RefundList"];
export type Selection = Schemas["SelectionItem"];

export type TraceStep = Schemas["TraceStep"];
export type TraceResponse = Schemas["TraceResponse"];
export type Metrics = Schemas["Metrics"];

// --- SSE stream types (hand-written; no OpenAPI representation) ---

export type Eligibility = "eligible" | "final_sale" | "window_expired" | "not_delivered";

export interface ReturnItem {
  line_ref: string;
  product_name: string;
  unit_price: string;
  remaining_quantity: number;
  eligibility: Eligibility;
  eligibility_note: string;
}

export interface ReturnSelectorPayload {
  order_number: string;
  items: ReturnItem[];
  threshold_usd: string;
  already_refunded_total: string;
}

export interface DecisionPayload {
  outcome: string;
  item: string | null;
  amount: string | null;
  reason: string;
}

export type SSEEvent =
  | { type: "token"; data: { text: string } }
  | { type: "tool_call"; data: { tool: string; summary: string } }
  | { type: "tool_result"; data: { tool: string; status: string } }
  | { type: "return_selector"; data: ReturnSelectorPayload }
  | { type: "decision"; data: DecisionPayload }
  | { type: "done"; data: Record<string, never> }
  | { type: "error"; data: { code: string; message: string } };
