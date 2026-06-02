import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ReturnSelectorPayload } from "../../api/types";
import { ReturnSelector } from "./ReturnSelector";

const PAYLOAD: ReturnSelectorPayload = {
  order_number: "ORD-1002",
  items: [
    {
      line_ref: "Water Bottle",
      product_name: "Water Bottle",
      unit_price: "50.00",
      remaining_quantity: 2,
      eligibility: "eligible",
      eligibility_note: "",
    },
    {
      line_ref: "Clearance Tee",
      product_name: "Clearance Tee",
      unit_price: "80.00",
      remaining_quantity: 1,
      eligibility: "final_sale",
      eligibility_note: "Final sale — not returnable",
    },
  ],
  threshold_usd: "500",
  already_refunded_total: "0",
};

describe("ReturnSelector", () => {
  it("disables ineligible rows and shows the reason", () => {
    render(<ReturnSelector payload={PAYLOAD} locked={false} onConfirm={() => {}} />);
    const finalSale = screen.getByLabelText("Select Clearance Tee") as HTMLInputElement;
    expect(finalSale).toBeDisabled();
    expect(screen.getByText("Final sale — not returnable")).toBeInTheDocument();
  });

  it("tracks running total and confirms the exact selection", () => {
    const onConfirm = vi.fn();
    render(<ReturnSelector payload={PAYLOAD} locked={false} onConfirm={onConfirm} />);

    fireEvent.click(screen.getByLabelText("Select Water Bottle"));
    fireEvent.change(screen.getByLabelText("Quantity for Water Bottle"), { target: { value: "2" } });

    expect(screen.getByTestId("running-total")).toHaveTextContent("100.00");

    fireEvent.click(screen.getByRole("button", { name: "Confirm return" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    const [selection, message] = onConfirm.mock.calls[0];
    expect(selection).toEqual([{ line_ref: "Water Bottle", quantity: 2 }]);
    expect(message).toContain("ORD-1002");
  });

  it("shows the over-threshold hint when projected total exceeds the limit", () => {
    const over: ReturnSelectorPayload = { ...PAYLOAD, threshold_usd: "10" };
    render(<ReturnSelector payload={over} locked={false} onConfirm={() => {}} />);
    fireEvent.click(screen.getByLabelText("Select Water Bottle"));
    expect(screen.getByTestId("threshold-hint")).toBeInTheDocument();
  });

  it("locks after submit", () => {
    render(<ReturnSelector payload={PAYLOAD} locked onConfirm={() => {}} />);
    expect(screen.getByRole("button", { name: "Submitted" })).toBeDisabled();
    expect(screen.getByLabelText("Select Water Bottle")).toBeDisabled();
  });
});
