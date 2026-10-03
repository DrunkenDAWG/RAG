// src/components/Chat/ChatInput.tsx
import { Send, Square, GraduationCap, Sparkles } from "lucide-react";
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
      className="flex flex-col px-4 py-3 border-t border-slate-700/60 bg-slate-900/80 backdrop-blur"
    >
      {/* Tutor Mode Toggle Bar */}
      <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <div
            className={clsx(
              "flex items-center justify-center w-5 h-5 rounded-md transition-colors",
              tutorMode ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400",
            )}
          >
            <GraduationCap size={13} />
          </div>
          <span className="text-xs font-medium text-slate-300">
            Tutor Mode (Ask me questions)
          </span>
          {tutorMode && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              <Sparkles size={10} /> Socratic Active
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => onToggleTutorMode(!tutorMode)}
          disabled={disabled}
          className={clsx(
            "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
            tutorMode ? "bg-indigo-600" : "bg-slate-700",
            disabled && "opacity-50 cursor-not-allowed",
          )}
          title={tutorMode ? "Disable Tutor Mode" : "Enable Socratic Tutor Mode"}
        >
          <span
            className={clsx(
              "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
              tutorMode ? "translate-x-4" : "translate-x-0",
            )}
          />
        </button>
      </div>

      <div className="flex items-end gap-3">
        <textarea
          ref={textareaRef}
          rows={1}
          disabled={disabled}
          onKeyDown={handleKeyDown}
          placeholder={
            disabled
              ? "Select or create a session first…"
              : tutorMode
              ? "Ask a concept or problem to solve together with your Socratic tutor…"
              : "Ask a question about your documents… (Shift+Enter for newline)"
          }
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
      </div>
    </form>
  );
}
