import type { RefundItem } from "../../api/types";

const STATUS_STYLE: Record<string, string> = {
  approved: "text-green-700",
  denied: "text-red-700",
  escalated: "text-amber-700",
};

export function RefundTable({ refunds }: { refunds: RefundItem[] }) {
  if (refunds.length === 0) {
    return <p className="text-sm text-gray-400">No refunds yet.</p>;
  }
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="text-left text-xs text-gray-500">
          <th className="py-1" scope="col">Order</th>
          <th scope="col">Item</th>
          <th scope="col">Qty</th>
          <th scope="col">Amount</th>
          <th scope="col">Status</th>
          <th scope="col">Reason</th>
          <th scope="col">By</th>
        </tr>
      </thead>
      <tbody>
        {refunds.map((r, i) => (
          <tr key={i} className="border-t">
            <td className="py-1">{r.order_number}</td>
            <td>{r.item}</td>
            <td>{r.quantity}</td>
            <td>${r.amount}</td>
            <td className={STATUS_STYLE[r.status] ?? ""}>{r.status}</td>
            <td className="text-xs text-gray-600">{r.reason ?? r.reason_code}</td>
            <td className="text-xs">{r.decided_by}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
