// Interactive Return Selector (docs/components/06 §4). The eligibility hints are
// UI-only; process_refund re-validates server-side at confirm. Ineligible rows
// are shown but disabled with the reason (transparency).

import { useMemo, useState } from "react";

import type { ReturnSelectorPayload, Selection } from "../../api/types";

interface RowState {
  checked: boolean;
  qty: number;
}

const NOTE: Record<string, string> = {
  final_sale: "Final sale — not returnable",
  window_expired: "Return window closed",
  not_delivered: "Not yet delivered",
};

export function ReturnSelector({
  payload,
  locked,
  onConfirm,
}: {
  payload: ReturnSelectorPayload;
  locked: boolean;
  onConfirm: (selection: Selection[], message: string) => void;
}) {
  const [rows, setRows] = useState<Record<string, RowState>>(() =>
    Object.fromEntries(payload.items.map((i) => [i.line_ref, { checked: false, qty: 1 }])),
  );

  const update = (lineRef: string, patch: Partial<RowState>) =>
    setRows((prev) => ({ ...prev, [lineRef]: { ...prev[lineRef], ...patch } }));

  const total = useMemo(() => {
    return payload.items.reduce((sum, item) => {
      const row = rows[item.line_ref];
      if (item.eligibility === "eligible" && row.checked) {
        return sum + parseFloat(item.unit_price) * row.qty;
      }
      return sum;
    }, 0);
  }, [payload.items, rows]);

  const projected = parseFloat(payload.already_refunded_total) + total;
  const overThreshold = projected > parseFloat(payload.threshold_usd);
  const anyChecked = payload.items.some(
    (i) => i.eligibility === "eligible" && rows[i.line_ref].checked,
  );

  const confirm = () => {
    if (locked || !anyChecked) return;
    const selection: Selection[] = [];
    const parts: string[] = [];
    for (const item of payload.items) {
      const row = rows[item.line_ref];
      if (item.eligibility === "eligible" && row.checked) {
        selection.push({ line_ref: item.line_ref, quantity: row.qty });
        parts.push(`${row.qty} × ${item.product_name}`);
      }
    }
    onConfirm(selection, `Return ${parts.join(", ")} — ${payload.order_number}`);
  };

  return (
    <div className="rounded-xl border bg-white p-3 text-sm">
      <div className="mb-2 font-medium">Select items to return — {payload.order_number}</div>
      <table className="w-full border-collapse">
        <caption className="sr-only">Returnable items for {payload.order_number}</caption>
        <thead>
          <tr className="text-left text-xs text-gray-500">
            <th className="py-1" scope="col">Select</th>
            <th scope="col">Item</th>
            <th scope="col">Unit price</th>
            <th scope="col">Available</th>
            <th scope="col">Quantity</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
          {payload.items.map((item) => {
            const eligible = item.eligibility === "eligible";
            const row = rows[item.line_ref];
            return (
              <tr
                key={item.line_ref}
                aria-disabled={!eligible}
                className={!eligible ? "text-gray-400" : ""}
              >
                <td className="py-1">
                  <input
                    type="checkbox"
                    aria-label={`Select ${item.product_name}`}
                    checked={row.checked}
                    disabled={!eligible || locked}
                    onChange={(e) => update(item.line_ref, { checked: e.target.checked })}
                  />
                </td>
                <td>{item.product_name}</td>
                <td>${parseFloat(item.unit_price).toFixed(2)}</td>
                <td>{item.remaining_quantity}</td>
                <td>
                  <select
                    aria-label={`Quantity for ${item.product_name}`}
                    value={row.qty}
                    disabled={!eligible || !row.checked || locked}
                    onChange={(e) => update(item.line_ref, { qty: Number(e.target.value) })}
                  >
                    {Array.from({ length: item.remaining_quantity }, (_, n) => n + 1).map((q) => (
                      <option key={q} value={q}>
                        {q}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="text-xs">{eligible ? "" : NOTE[item.eligibility] ?? "Not eligible"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-3 flex items-center justify-between">
        <span data-testid="running-total">Refund total: ${total.toFixed(2)}</span>
        <button
          type="button"
          onClick={confirm}
          disabled={locked || !anyChecked}
          className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white disabled:opacity-40"
        >
          {locked ? "Submitted" : "Confirm return"}
        </button>
      </div>
      {overThreshold ? (
        <div data-testid="threshold-hint" className="mt-2 text-xs text-amber-700">
          This selection may require human review (over ${payload.threshold_usd}).
        </div>
      ) : null}
    </div>
  );
}
