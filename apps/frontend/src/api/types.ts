// Shared API types. The SSE event union is hand-written (it mirrors
// app/agent/events.py) because OpenAPI can't describe an event stream
// (docs/components/06 §2-3). The rest mirror the backend response models.

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

export interface Selection {
  line_ref: string;
  quantity: number;
}

export interface ConversationCreated {
  conversation_id: string;
  status: string;
  created_at: string;
}

export interface MessageOut {
  role: string;
  content: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  status: string;
  customer_name: string | null;
  messages: MessageOut[];
}

export interface AdminConversationItem {
  id: string;
  customer_name: string | null;
  status: string;
  last_decision: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminConversationList {
  items: AdminConversationItem[];
  total: number;
}

export interface TraceStep {
  step_no: number;
  type: string;
  tool_name: string | null;
  tool_input: unknown;
  tool_output: unknown;
  latency_ms: number | null;
  created_at: string;
}

export interface TraceResponse {
  conversation: { id: string; status: string; customer_name: string | null; created_at: string };
  messages: MessageOut[];
  steps: TraceStep[];
}

export interface RefundItem {
  order_number: string;
  item: string;
  quantity: number;
  amount: string;
  status: string;
  reason_code: string;
  reason: string | null;
  decided_by: string;
  created_at: string;
}

export interface RefundList {
  items: RefundItem[];
  total: number;
}

export interface Metrics {
  approved: number;
  denied: number;
  escalated: number;
  needs_info: number;
  total: number;
  approval_rate: number;
  escalation_rate: number;
}
