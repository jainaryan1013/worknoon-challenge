import type { Metrics } from "../../api/types";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-center">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

export function MetricsBar({ metrics }: { metrics: Metrics }) {
  const pct = (n: number) => `${Math.round(n * 100)}%`;
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
      <Stat label="Approved" value={metrics.approved} />
      <Stat label="Denied" value={metrics.denied} />
      <Stat label="Escalated" value={metrics.escalated} />
      <Stat label="Needs info" value={metrics.needs_info} />
      <Stat label="Approval rate" value={pct(metrics.approval_rate)} />
      <Stat label="Escalation rate" value={pct(metrics.escalation_rate)} />
    </div>
  );
}
