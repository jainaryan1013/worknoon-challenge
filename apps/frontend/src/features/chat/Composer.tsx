import { useState } from "react";

export function Composer({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <form onSubmit={submit} className="flex gap-2 border-t p-3">
      <input
        className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none focus:border-blue-400"
        placeholder="Ask about a refund or return…"
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        aria-label="Message"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
      >
        Send
      </button>
    </form>
  );
}
