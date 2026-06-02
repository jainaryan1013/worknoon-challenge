import type { DecisionPayload } from "../../api/types";

const STYLES: Record<string, string> = {
  APPROVE: "bg-green-100 text-green-800 border-green-300",
  DENY: "bg-red-100 text-red-800 border-red-300",
  ESCALATE: "bg-amber-100 text-amber-800 border-amber-300",
  NEEDS_INFO: "bg-gray-100 text-gray-700 border-gray-300",
};

const LABEL: Record<string, string> = {
  APPROVE: "Approved",
  DENY: "Denied",
  ESCALATE: "Escalated",
  NEEDS_INFO: "Needs info",
};

export function DecisionBadge({ decision }: { decision: DecisionPayload }) {
  const style = STYLES[decision.outcome] ?? STYLES.NEEDS_INFO;
  const label = LABEL[decision.outcome] ?? decision.outcome;
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${style}`} role="status">
      <span className="font-semibold">{label}</span>
      {decision.item ? <span className="ml-1">· {decision.item}</span> : null}
      {decision.amount && decision.outcome === "APPROVE" ? (
        <span className="ml-1">· ${decision.amount}</span>
      ) : null}
      <div className="mt-1 text-xs opacity-80">{decision.reason}</div>
    </div>
  );
}
