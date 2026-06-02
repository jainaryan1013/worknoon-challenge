import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Metrics, RefundItem, TraceResponse } from "../../api/types";
import { MetricsBar } from "./MetricsBar";
import { RefundTable } from "./RefundTable";
import { TraceTimeline } from "./TraceTimeline";

const TRACE: TraceResponse = {
  conversation: { id: "c1", status: "active", customer_name: "Ada Lovelace", created_at: "2026-01-01T00:00:00Z" },
  messages: [],
  steps: [
    { step_no: 1, type: "model_text", tool_name: null, tool_input: null, tool_output: null, latency_ms: null, created_at: "" },
    { step_no: 2, type: "tool_call", tool_name: "process_refund", tool_input: { quantity: 1 }, tool_output: null, latency_ms: 12, created_at: "" },
    { step_no: 3, type: "tool_result", tool_name: "process_refund", tool_input: null, tool_output: { ok: true }, latency_ms: null, created_at: "" },
    { step_no: 4, type: "decision", tool_name: "process_refund", tool_input: null, tool_output: { outcome: "APPROVE" }, latency_ms: null, created_at: "" },
  ],
};

describe("admin views", () => {
  it("TraceTimeline renders each step type", () => {
    render(<TraceTimeline trace={TRACE} />);
    expect(screen.getByText(/Model reasoning/)).toBeInTheDocument();
    expect(screen.getByText(/Tool call · process_refund/)).toBeInTheDocument();
    expect(screen.getByText(/Tool result · process_refund/)).toBeInTheDocument();
    expect(screen.getByText(/Decision · process_refund/)).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("MetricsBar renders counts and rates", () => {
    const m: Metrics = {
      approved: 5, denied: 2, escalated: 1, needs_info: 0, total: 8,
      approval_rate: 0.625, escalation_rate: 0.125,
    };
    render(<MetricsBar metrics={m} />);
    expect(screen.getByText("63%")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("RefundTable lists refunds incl. denials", () => {
    const refunds: RefundItem[] = [
      { order_number: "ORD-1", item: "Mouse", quantity: 1, amount: "120.00", status: "approved", reason_code: "APPROVED", reason: "ok", decided_by: "agent", created_at: "" },
      { order_number: "ORD-2", item: "Tee", quantity: 1, amount: "0.00", status: "denied", reason_code: "DENIED_FINAL_SALE", reason: "final sale", decided_by: "agent", created_at: "" },
    ];
    render(<RefundTable refunds={refunds} />);
    expect(screen.getByText("denied")).toBeInTheDocument();
    expect(screen.getByText("Mouse")).toBeInTheDocument();
  });
});
