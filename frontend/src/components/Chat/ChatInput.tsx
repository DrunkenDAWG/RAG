// src/components/Chat/ChatInput.tsx
// Upgraded to React Bits Pro "Prompt Input 3" (Hero Launcher with Suggestions & History)
// Restyled for strict monochrome B2B SaaS aesthetic (Vercel / Linear)

import { useState } from "react";
import { GraduationCap, Sparkles, BookOpen, Brain, HelpCircle } from "lucide-react";
import clsx from "clsx";
import { PromptInput3, type SuggestionChip } from "@/components/ui/prompt-input-3";

interface Props {
  isStreaming: boolean;
  disabled: boolean;
  tutorMode: boolean;
  onToggleTutorMode: (val: boolean) => void;
  onSend: (query: string) => void;
  onStop: () => void;
}

const STORAGE_KEY = "rag_recent_prompts";

export function ChatInput({
  isStreaming,
  disabled,
  tutorMode,
  onToggleTutorMode,
  onSend,
  onStop,
}: Props) {
  const [recentPrompts, setRecentPrompts] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const saveRecentPrompt = (prompt: string) => {
    setRecentPrompts((prev) => {
      const filtered = prev.filter((p) => p.toLowerCase() !== prompt.toLowerCase());
      const next = [prompt, ...filtered].slice(0, 10);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore storage quota error
      }
      return next;
    });
  };

  const handleClearRecent = () => {
    setRecentPrompts([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  };

  const handleSend = (query: string) => {
    saveRecentPrompt(query);
    onSend(query);
  };

  // Contextual suggestion chips for Hero Launcher
  const suggestions: SuggestionChip[] = tutorMode
    ? [
        {
          label: "Test my knowledge",
          prompt: "Ask me a Socratic follow-up question to test my understanding of the notes.",
          icon: <HelpCircle size={11} />,
        },
        {
          label: "Guide step-by-step",
          prompt: "Guide me through solving the primary problem described in the uploaded notes step-by-step.",
          icon: <Brain size={11} />,
        },
        {
          label: "Give me a hint",
          prompt: "Give me a subtle conceptual hint about the core mechanism without revealing the full answer.",
          icon: <Sparkles size={11} />,
        },
      ]
    : [
        {
          label: "Summarize notes",
          prompt: "Provide a comprehensive, high-yield summary of the uploaded study documents.",
          icon: <BookOpen size={11} />,
        },
        {
          label: "Key concepts",
          prompt: "What are the top 5 core principles and definitions in these notes?",
          icon: <Sparkles size={11} />,
        },
        {
          label: "Compare mechanisms",
          prompt: "Compare and contrast the main methods or mechanisms discussed in the source documents.",
          icon: <Brain size={11} />,
        },
      ];

  const headerSlot = (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div
          className={clsx(
            "flex items-center justify-center w-4 h-4 rounded transition-colors",
            tutorMode
              ? "bg-white text-black"
              : "bg-neutral-900 text-neutral-400 border border-neutral-800",
          )}
        >
          <GraduationCap size={10} />
        </div>
        <span className="text-xs font-medium text-neutral-300">
          Socratic Tutor Mode
        </span>
        {tutorMode ? (
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-neutral-900 text-white border border-neutral-700">
            Active
          </span>
        ) : (
          <span className="text-[10px] font-mono text-neutral-500">
            Standard Q&A
          </span>
        )}
      </div>

      <button
        type="button"
        onClick={() => onToggleTutorMode(!tutorMode)}
        disabled={disabled}
        className={clsx(
          "relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border border-neutral-800 transition-colors duration-150 ease-in-out focus:outline-none",
          tutorMode ? "bg-white" : "bg-neutral-900",
          disabled && "opacity-40 cursor-not-allowed",
        )}
        title={tutorMode ? "Disable Tutor Mode" : "Enable Socratic Tutor Mode"}
      >
        <span
          className={clsx(
            "pointer-events-none inline-block h-3 w-3 transform rounded-full transition duration-150 ease-in-out mt-[1px]",
            tutorMode ? "translate-x-3.5 bg-black" : "translate-x-0.5 bg-neutral-500",
          )}
        />
      </button>
    </div>
  );

  return (
    <div className="px-6 py-4 border-t border-border-subtle bg-surface/90 backdrop-blur-md">
      <PromptInput3
        disabled={disabled}
        isStreaming={isStreaming}
        onStop={onStop}
        onSubmitPrompt={handleSend}
        suggestions={suggestions}
        recentPrompts={recentPrompts}
        onSelectRecent={handleSend}
        onClearRecent={handleClearRecent}
        headerSlot={headerSlot}
        placeholder={
          disabled
            ? "Select or create a session first…"
            : tutorMode
            ? "Ask a concept or problem to solve together with your tutor…"
            : "Ask a question about your documents… (Enter to send, Shift+Enter for newline)"
        }
      />
    </div>
  );
}
