import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAdminConversations, getMetrics, getRefunds, getTrace } from "../../api/client";
import { ConversationList } from "./ConversationList";
import { MetricsBar } from "./MetricsBar";
import { RefundTable } from "./RefundTable";
import { TraceTimeline } from "./TraceTimeline";

export function AdminPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  const convs = useQuery({
    queryKey: ["admin-convs", status],
    queryFn: () => getAdminConversations(status || undefined),
  });
  const metrics = useQuery({ queryKey: ["admin-metrics"], queryFn: getMetrics });
  const refunds = useQuery({ queryKey: ["admin-refunds"], queryFn: () => getRefunds() });
  const trace = useQuery({
    queryKey: ["admin-trace", selectedId],
    queryFn: () => getTrace(selectedId as string),
    enabled: Boolean(selectedId),
  });

  const reload = () => {
    void convs.refetch();
    void metrics.refetch();
    void refunds.refetch();
    if (selectedId) void trace.refetch();
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4">
      <header className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Admin · Reasoning Dashboard</h1>
        <button
          type="button"
          onClick={reload}
          className="rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-50"
        >
          Reload
        </button>
      </header>

      {metrics.data ? <MetricsBar metrics={metrics.data} /> : null}

      <div className="grid gap-4 md:grid-cols-[20rem_1fr]">
        <aside className="space-y-2">
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-lg border px-2 py-1 text-sm"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
          </select>
          {convs.data ? (
            <ConversationList
              items={convs.data.items}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          ) : (
            <p className="text-sm text-gray-400">Loading…</p>
          )}
        </aside>

        <section>
          {selectedId == null ? (
            <p className="text-sm text-gray-400">Select a conversation to view its trace.</p>
          ) : trace.data ? (
            <TraceTimeline trace={trace.data} />
          ) : (
            <p className="text-sm text-gray-400">Loading trace…</p>
          )}
        </section>
      </div>

      <section className="space-y-2">
        <h2 className="text-base font-semibold">Refund audit</h2>
        {refunds.data ? <RefundTable refunds={refunds.data.items} /> : null}
      </section>
    </div>
  );
}
