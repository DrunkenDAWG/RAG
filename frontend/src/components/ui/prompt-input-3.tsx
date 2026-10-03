// src/components/ui/prompt-input-3.tsx
// React Bits Pro: Prompt Input 3 (Hero Prompt Launcher with Suggestion Chips & Recent History)
// Restyled for strict monochrome B2B SaaS design system (Vercel / Linear style)

import * as React from "react";
import {
  ArrowUp,
  Square,
  History,
  Sparkles,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface SuggestionChip {
  id?: string;
  label: string;
  icon?: React.ReactNode;
  prompt?: string;
}

export interface PromptInput3Props
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "onSubmit"> {
  isStreaming?: boolean;
  onStop?: () => void;
  onSubmitPrompt?: (prompt: string) => void;
  suggestions?: (string | SuggestionChip)[];
  recentPrompts?: string[];
  onSelectRecent?: (prompt: string) => void;
  onClearRecent?: () => void;
  headerSlot?: React.ReactNode;
  footerSlot?: React.ReactNode;
  actionSlot?: React.ReactNode;
}

export const PromptInput3 = React.forwardRef<HTMLTextAreaElement, PromptInput3Props>(
  (
    {
      className,
      value,
      defaultValue,
      onChange,
      onKeyDown,
      placeholder = "Ask a question about your documents…",
      disabled = false,
      isStreaming = false,
      onStop,
      onSubmitPrompt,
      suggestions = [],
      recentPrompts = [],
      onSelectRecent,
      onClearRecent,
      headerSlot,
      footerSlot,
      actionSlot,
      ...props
    },
    ref,
  ) => {
    const internalRef = React.useRef<HTMLTextAreaElement | null>(null);
    const [inputValue, setInputValue] = React.useState<string>(
      (value as string) ?? (defaultValue as string) ?? "",
    );
    const [historyOpen, setHistoryOpen] = React.useState(false);
    const historyRef = React.useRef<HTMLDivElement>(null);

    // Sync controlled value
    React.useEffect(() => {
      if (value !== undefined) {
        setInputValue(value as string);
      }
    }, [value]);

    // Forward both internal ref and external forwarded ref
    React.useImperativeHandle(ref, () => internalRef.current as HTMLTextAreaElement);

    // Auto-adjust textarea height
    React.useEffect(() => {
      const el = internalRef.current;
      if (!el) return;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    }, [inputValue]);

    // Close history dropdown on outside click
    React.useEffect(() => {
      if (!historyOpen) return;
      const handleClickOutside = (e: MouseEvent) => {
        if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
          setHistoryOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [historyOpen]);

    const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (value === undefined) {
        setInputValue(e.target.value);
      }
      onChange?.(e);
    };

    const handleFormSubmit = (e?: React.FormEvent) => {
      e?.preventDefault();
      const trimmed = inputValue.trim();
      if (!trimmed || isStreaming || disabled) return;

      onSubmitPrompt?.(trimmed);

      if (value === undefined) {
        setInputValue("");
        if (internalRef.current) {
          internalRef.current.value = "";
          internalRef.current.style.height = "auto";
        }
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleFormSubmit();
      }
      onKeyDown?.(e);
    };

    const handleSuggestionClick = (suggestion: string | SuggestionChip) => {
      const promptText =
        typeof suggestion === "string" ? suggestion : suggestion.prompt ?? suggestion.label;

      if (value === undefined) {
        setInputValue(promptText);
        if (internalRef.current) {
          internalRef.current.focus();
        }
      } else {
        onSubmitPrompt?.(promptText);
      }
    };

    const handleHistoryClick = (prompt: string) => {
      setHistoryOpen(false);
      if (onSelectRecent) {
        onSelectRecent(prompt);
      } else if (value === undefined) {
        setInputValue(prompt);
        if (internalRef.current) {
          internalRef.current.focus();
        }
      } else {
        onSubmitPrompt?.(prompt);
      }
    };

    return (
      <div
        className={cn(
          "w-full flex flex-col gap-2.5",
          className,
        )}
      >
        {/* Suggestion Chips (Hero Launcher bar) */}
        {suggestions.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar select-none">
            <span className="flex items-center gap-1 text-[11px] font-mono text-neutral-500 shrink-0">
              <Sparkles size={11} />
              <span>Suggested:</span>
            </span>
            {suggestions.map((item, idx) => {
              const label = typeof item === "string" ? item : item.label;
              const icon = typeof item === "object" ? item.icon : null;
              return (
                <button
                  key={idx}
                  type="button"
                  disabled={disabled || isStreaming}
                  onClick={() => handleSuggestionClick(item)}
                  className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono bg-transparent hover:bg-neutral-900 border border-neutral-800 hover:border-neutral-700 text-neutral-400 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {icon}
                  <span>{label}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Hero Input Container */}
        <div
          className={cn(
            "relative flex flex-col rounded-xl bg-surface border border-neutral-800 transition-all duration-150",
            "focus-within:border-neutral-600 focus-within:ring-1 focus-within:ring-neutral-600",
            disabled && "opacity-40 cursor-not-allowed",
          )}
        >
          {/* Optional Header Slot (e.g. Mode Switchers, Model Selector, Context Badges) */}
          {headerSlot && (
            <div className="px-3.5 pt-3 pb-2 border-b border-neutral-800/80">
              {headerSlot}
            </div>
          )}

          {/* Text Area */}
          <div className="px-3.5 pt-3 pb-2">
            <textarea
              ref={internalRef}
              rows={1}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              placeholder={placeholder}
              className="w-full resize-none bg-transparent text-xs sm:text-sm text-primary placeholder:text-neutral-500 outline-none leading-relaxed min-h-[44px] max-h-[180px] overflow-y-auto"
              {...props}
            />
          </div>

          {/* Bottom Action Toolbar */}
          <div className="flex items-center justify-between px-3 py-2 border-t border-neutral-800/60 bg-surface/80 rounded-b-xl">
            {/* Left toolbar items: History launcher & custom actions */}
            <div className="flex items-center gap-2 relative" ref={historyRef}>
              {recentPrompts.length > 0 && (
                <div className="relative">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => setHistoryOpen((prev) => !prev)}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-mono text-neutral-400 hover:text-white hover:bg-neutral-900 border border-transparent hover:border-neutral-800 transition-colors cursor-pointer"
                    title="Recent prompts"
                  >
                    <History size={12} />
                    <span>Recent</span>
                    <ChevronDown size={10} className="text-neutral-500" />
                  </button>

                  {/* Recent History Dropdown */}
                  {historyOpen && (
                    <div className="absolute bottom-full left-0 mb-2 w-72 max-h-60 overflow-y-auto rounded-lg bg-surface border border-neutral-700 shadow-modal z-50 p-1 flex flex-col gap-0.5 animate-in fade-in duration-100">
                      <div className="flex items-center justify-between px-2 py-1.5 border-b border-neutral-800 text-[10px] font-mono uppercase tracking-wider text-neutral-500">
                        <span>Recent Prompts</span>
                        {onClearRecent && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onClearRecent();
                              setHistoryOpen(false);
                            }}
                            className="text-neutral-500 hover:text-neutral-300 cursor-pointer"
                          >
                            Clear
                          </button>
                        )}
                      </div>

                      {recentPrompts.map((prompt, pIdx) => (
                        <button
                          key={pIdx}
                          type="button"
                          onClick={() => handleHistoryClick(prompt)}
                          className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded text-left text-xs text-neutral-300 hover:text-white hover:bg-neutral-800 transition-colors cursor-pointer group"
                        >
                          <span className="truncate flex-1">{prompt}</span>
                          <span className="text-[10px] font-mono text-neutral-600 group-hover:text-neutral-400">
                            ↵
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {actionSlot}
            </div>

            {/* Right toolbar items: Submit / Stop */}
            <div className="flex items-center gap-2">
              {isStreaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  title="Stop generating"
                  className="flex items-center justify-center w-8 h-8 rounded-md bg-neutral-900 border border-neutral-800 hover:border-neutral-700 text-white transition-all active:scale-95 cursor-pointer"
                >
                  <Square size={12} />
                </button>
              ) : (
                <button
                  type="button"
                  disabled={disabled || !inputValue.trim()}
                  onClick={handleFormSubmit}
                  title="Send prompt"
                  className={cn(
                    "flex items-center justify-center w-8 h-8 rounded-md font-medium transition-all shadow-sm cursor-pointer",
                    disabled || !inputValue.trim()
                      ? "bg-neutral-900 text-neutral-600 border border-neutral-800 cursor-not-allowed opacity-40"
                      : "bg-white text-black hover:bg-neutral-200 active:scale-95",
                  )}
                >
                  <ArrowUp size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Optional Footer Slot */}
          {footerSlot && (
            <div className="px-3 pb-2 pt-1 border-t border-neutral-800/40">
              {footerSlot}
            </div>
          )}
        </div>
      </div>
    );
  },
);

PromptInput3.displayName = "PromptInput3";
export default PromptInput3;
