import { ChatWindow } from "./ChatWindow";
import { Composer } from "./Composer";
import { useChatStream } from "./useChatStream";

export function ChatPage() {
  const chat = useChatStream();

  return (
    <div className="mx-auto flex h-[100dvh] max-w-2xl flex-col">
      <header className="border-b p-4">
        <h1 className="text-lg font-semibold">Refund Support</h1>
      </header>

      <ChatWindow
        messages={chat.messages}
        toolStatus={chat.toolStatus}
        decisions={chat.decisions}
        selector={chat.selector}
        onConfirm={chat.confirmSelection}
      />

      {chat.error ? (
        <div className="mx-4 mb-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {chat.error}
        </div>
      ) : null}

      <Composer disabled={chat.streaming} onSend={(text) => void chat.send(text)} />
    </div>
  );
}
