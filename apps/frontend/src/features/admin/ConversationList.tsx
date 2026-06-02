import type { AdminConversationItem } from "../../api/types";

export function ConversationList({
  items,
  selectedId,
  onSelect,
}: {
  items: AdminConversationItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-400">No conversations.</p>;
  }
  return (
    <ul className="divide-y rounded-lg border bg-white">
      {items.map((c) => (
        <li key={c.id}>
          <button
            type="button"
            onClick={() => onSelect(c.id)}
            className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50 ${
              selectedId === c.id ? "bg-blue-50" : ""
            }`}
          >
            <span>
              <span className="font-medium">{c.customer_name ?? "Unverified"}</span>
              <span className="ml-2 text-xs text-gray-500">{c.message_count} msgs</span>
            </span>
            <span className="flex items-center gap-2 text-xs">
              {c.last_decision ? <span className="text-gray-600">{c.last_decision}</span> : null}
              <span className="rounded bg-gray-100 px-2 py-0.5">{c.status}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
