// src/components/Chat/ChatInput.tsx
import { Send, Square } from "lucide-react";
import { useRef, useEffect, type KeyboardEvent, type FormEvent } from "react";
import clsx from "clsx";

interface Props {
  isStreaming: boolean;
  disabled: boolean;
  onSend: (query: string) => void;
  onStop: () => void;
}

export function ChatInput({ isStreaming, disabled, onSend, onStop }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  });

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const val = textareaRef.current?.value.trim();
    if (!val || isStreaming) return;
    onSend(val);
    if (textareaRef.current) {
      textareaRef.current.value = "";
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 px-4 py-3 border-t border-slate-700/60 bg-slate-900/80 backdrop-blur"
    >
      <textarea
        ref={textareaRef}
        rows={1}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Select or create a session first…" : "Ask a question about your documents… (Shift+Enter for newline)"}
        className={clsx(
          "flex-1 resize-none rounded-xl bg-slate-800 border border-slate-700 px-4 py-3 text-sm text-slate-100",
          "placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors",
          "max-h-[200px] overflow-y-auto",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      />
      {isStreaming ? (
        <button
          type="button"
          onClick={onStop}
          title="Stop generation"
          className="shrink-0 flex items-center justify-center w-10 h-10 rounded-xl bg-red-600 hover:bg-red-500 text-white transition-colors"
        >
          <Square size={16} />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled}
          title="Send message"
          className={clsx(
            "shrink-0 flex items-center justify-center w-10 h-10 rounded-xl transition-colors",
            disabled
              ? "bg-slate-700 text-slate-500 cursor-not-allowed"
              : "bg-indigo-600 hover:bg-indigo-500 text-white",
          )}
        >
          <Send size={16} />
        </button>
      )}
    </form>
  );
}
