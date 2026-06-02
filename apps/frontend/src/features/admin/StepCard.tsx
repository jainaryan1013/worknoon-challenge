import type { TraceStep } from "../../api/types";

const LABEL: Record<string, string> = {
  model_text: "Model reasoning",
  tool_call: "Tool call",
  tool_result: "Tool result",
  decision: "Decision",
};

function Json({ value }: { value: unknown }) {
  if (value === null || value === undefined) return null;
  return (
    <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-xs text-gray-700">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function StepCard({ step }: { step: TraceStep }) {
  return (
    <div className="rounded-lg border bg-white p-3">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span className="font-medium text-gray-700">
          #{step.step_no} · {LABEL[step.type] ?? step.type}
          {step.tool_name ? ` · ${step.tool_name}` : ""}
        </span>
        {step.latency_ms != null ? <span>{step.latency_ms} ms</span> : null}
      </div>
      {step.tool_input != null ? <Json value={step.tool_input} /> : null}
      {step.tool_output != null ? <Json value={step.tool_output} /> : null}
    </div>
  );
}
