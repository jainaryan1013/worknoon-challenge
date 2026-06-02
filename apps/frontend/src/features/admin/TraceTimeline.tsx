import type { TraceResponse } from "../../api/types";
import { StepCard } from "./StepCard";

export function TraceTimeline({ trace }: { trace: TraceResponse }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border bg-white p-3 text-sm">
        <div className="font-semibold">
          {trace.conversation.customer_name ?? "Unverified customer"}
        </div>
        <div className="text-xs text-gray-500">
          Status: {trace.conversation.status} · {trace.steps.length} steps
        </div>
      </div>
      {trace.steps.length === 0 ? (
        <p className="text-sm text-gray-400">No reasoning steps recorded yet.</p>
      ) : (
        trace.steps.map((s) => <StepCard key={s.step_no} step={s} />)
      )}
    </div>
  );
}
