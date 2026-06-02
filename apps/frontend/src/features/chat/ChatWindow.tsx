import type { DecisionPayload, Selection } from "../../api/types";
import { DecisionBadge } from "./DecisionBadge";
import { MessageBubble } from "./MessageBubble";
import { ReturnSelector } from "./ReturnSelector";
import { ToolStatus } from "./ToolStatus";
import type { ChatMessage, SelectorState } from "./useChatStream";

export function ChatWindow({
  messages,
  toolStatus,
  decisions,
  selector,
  onConfirm,
}: {
  messages: ChatMessage[];
  toolStatus: string | null;
  decisions: DecisionPayload[];
  selector: SelectorState | null;
  onConfirm: (selection: Selection[], message: string) => void;
}) {
  return (
    <div className="flex-1 space-y-3 overflow-y-auto p-4">
      {messages.length === 0 ? (
        <p className="text-center text-sm text-gray-400">
          Hi! I can help with refunds and returns. To start, share your order number and email.
        </p>
      ) : null}

      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}

      {toolStatus ? <ToolStatus summary={toolStatus} /> : null}

      {selector ? (
        <ReturnSelector payload={selector.payload} locked={selector.locked} onConfirm={onConfirm} />
      ) : null}

      {decisions.map((d, i) => (
        <DecisionBadge key={i} decision={d} />
      ))}
    </div>
  );
}
