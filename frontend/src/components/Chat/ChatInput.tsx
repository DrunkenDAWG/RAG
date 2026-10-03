// src/components/Chat/ChatInput.tsx
import { ArrowUp, Square, GraduationCap } from "lucide-react";
import { useRef, useEffect, type KeyboardEvent, type FormEvent } from "react";
import clsx from "clsx";

interface Props {
  isStreaming: boolean;
  disabled: boolean;
  tutorMode: boolean;
  onToggleTutorMode: (val: boolean) => void;
  onSend: (query: string) => void;
  onStop: () => void;
}

export function ChatInput({
  isStreaming,
  disabled,
  tutorMode,
  onToggleTutorMode,
  onSend,
  onStop,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
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
      className="flex flex-col px-6 py-4 border-t border-border-subtle bg-surface/90 backdrop-blur-md"
    >
      {/* Tutor Mode Toggle Bar */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <div
            className={clsx(
              "flex items-center justify-center w-5 h-5 rounded transition-colors",
              tutorMode ? "bg-white text-black" : "bg-subtle text-text-muted border border-border-subtle",
            )}
          >
            <GraduationCap size={12} />
          </div>
          <span className="text-xs font-medium text-text-secondary">
            Socratic Tutor Mode
          </span>
          {tutorMode && (
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-subtle text-text-primary border border-border-subtle">
              Active
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => onToggleTutorMode(!tutorMode)}
          disabled={disabled}
          className={clsx(
            "relative inline-flex h-4 w-8 shrink-0 cursor-pointer rounded-full border border-border-subtle transition-colors duration-200 ease-in-out focus:outline-none",
            tutorMode ? "bg-white" : "bg-subtle",
            disabled && "opacity-40 cursor-not-allowed",
          )}
          title={tutorMode ? "Disable Tutor Mode" : "Enable Socratic Tutor Mode"}
        >
          <span
            className={clsx(
              "pointer-events-none inline-block h-3 w-3 transform rounded-full transition duration-200 ease-in-out mt-[1px]",
              tutorMode ? "translate-x-4 bg-black" : "translate-x-0.5 bg-text-muted",
            )}
          />
        </button>
      </div>

      <div className="flex items-end gap-2.5">
        <textarea
          ref={textareaRef}
          rows={1}
          disabled={disabled}
          onKeyDown={handleKeyDown}
          placeholder={
            disabled
              ? "Select or create a session first…"
              : tutorMode
              ? "Ask a concept or problem to solve together with your tutor…"
              : "Ask a question about your documents… (Enter to send, Shift+Enter for newline)"
          }
          className={clsx(
            "flex-1 resize-none rounded-lg bg-canvas border border-border-subtle px-3.5 py-2.5 text-xs text-text-primary",
            "placeholder:text-text-muted focus:outline-none focus:border-border-strong transition-colors",
            "max-h-[180px] overflow-y-auto leading-relaxed",
            disabled && "opacity-40 cursor-not-allowed",
          )}
        />
        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            title="Stop generation"
            className="shrink-0 flex items-center justify-center w-9 h-9 rounded-lg bg-subtle border border-border-subtle hover:border-border-strong text-text-primary transition-all active:scale-95 cursor-pointer"
          >
            <Square size={13} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={disabled}
            title="Send message"
            className={clsx(
              "shrink-0 flex items-center justify-center w-9 h-9 rounded-lg font-medium transition-all cursor-pointer",
              disabled
                ? "bg-subtle text-text-muted border border-border-subtle cursor-not-allowed opacity-40"
                : "bg-white text-black hover:bg-neutral-200 active:scale-95 shadow-sm",
            )}
          >
            <ArrowUp size={15} />
          </button>
        )}
      </div>
    </form>
  );
}
