import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReturnSelectorPayload, SSEEvent } from "../../api/types";
import { useChatStream } from "./useChatStream";

const SELECTOR: ReturnSelectorPayload = {
  order_number: "ORD-1001",
  items: [
    {
      line_ref: "Wireless Mouse",
      product_name: "Wireless Mouse",
      unit_price: "120.00",
      remaining_quantity: 1,
      eligibility: "eligible",
      eligibility_note: "",
    },
  ],
  threshold_usd: "500",
  already_refunded_total: "0",
};

async function* scripted(): AsyncGenerator<SSEEvent> {
  yield { type: "tool_call", data: { tool: "verify_identity", summary: "Verifying…" } };
  yield { type: "return_selector", data: SELECTOR };
  yield { type: "decision", data: { outcome: "APPROVE", item: "Wireless Mouse", amount: "120.00", reason: "ok" } };
  yield { type: "token", data: { text: "All done." } };
  yield { type: "done", data: {} };
}

describe("useChatStream", () => {
  it("consumes a scripted SSE turn into UI state", async () => {
    const { result } = renderHook(() =>
      useChatStream({
        stream: () => scripted(),
        createConv: async () => ({ conversation_id: "c1" }),
      }),
    );

    await act(async () => {
      await result.current.send("refund my mouse");
    });

    await waitFor(() => expect(result.current.streaming).toBe(false));

    // user + assistant bubbles, assistant carries the streamed token
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({ role: "user", text: "refund my mouse" });
    expect(result.current.messages[1]).toMatchObject({ role: "assistant", text: "All done." });

    // selector rendered, decision badge captured, tool status cleared at end
    expect(result.current.selector?.payload.order_number).toBe("ORD-1001");
    expect(result.current.decisions).toHaveLength(1);
    expect(result.current.decisions[0].outcome).toBe("APPROVE");
    expect(result.current.toolStatus).toBeNull();
  });

  it("surfaces an error event as a message", async () => {
    async function* err(): AsyncGenerator<SSEEvent> {
      yield { type: "error", data: { code: "llm_unavailable", message: "try again" } };
      yield { type: "done", data: {} };
    }
    const { result } = renderHook(() =>
      useChatStream({ stream: () => err(), createConv: async () => ({ conversation_id: "c1" }) }),
    );
    await act(async () => {
      await result.current.send("hi");
    });
    await waitFor(() => expect(result.current.error).toBe("try again"));
  });
});
