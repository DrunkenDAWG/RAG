// src/components/Sidebar/StudyTools.tsx
import { useState, type FormEvent } from "react";
import { Sparkles, Brain, Loader2, HelpCircle, Layers, Info } from "lucide-react";
import clsx from "clsx";
import { generateQuiz, generateFlashcards } from "../../lib/api";
import type { FlashcardDeck, Quiz } from "../../types";

interface Props {
  sessionId: string | null;
  documentCount: number;
  onQuizGenerated: (quiz: Quiz, topic: string) => void;
  onFlashcardsGenerated: (deck: FlashcardDeck, topic: string) => void;
}

export function StudyTools({
  sessionId,
  documentCount,
  onQuizGenerated,
  onFlashcardsGenerated,
}: Props) {
  const [toolMode, setToolMode] = useState<"quiz" | "flashcards">("quiz");
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    const cleanTopic = topic.trim();
    if (!cleanTopic || !sessionId || loading) return;

    if (documentCount === 0) {
      setError("Upload at least one document first to extract study context.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (toolMode === "quiz") {
        const quiz = await generateQuiz(sessionId, cleanTopic);
        onQuizGenerated(quiz, cleanTopic);
      } else {
        const deck = await generateFlashcards(sessionId, cleanTopic);
        onFlashcardsGenerated(deck, cleanTopic);
      }
    } catch (err: any) {
      setError(
        err?.message || `Failed to generate ${toolMode}. Ensure documents are uploaded.`,
      );
    } finally {
      setLoading(false);
    }
  };

  const sampleTopics = ["Key Concepts", "Core Definitions", "Summary Review"];

  return (
    <div className="flex flex-col gap-4">
      {/* Title */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Brain size={15} className="text-text-secondary" />
          <h3 className="text-xs font-semibold text-text-primary tracking-tight">
            Active Recall
          </h3>
        </div>
        <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.2 rounded bg-subtle border border-border-subtle">
          Gemini Flash
        </span>
      </div>

      {/* Mode Switcher */}
      <div className="grid grid-cols-2 p-1 rounded-lg bg-canvas border border-border-subtle gap-1">
        <button
          type="button"
          onClick={() => {
            setToolMode("quiz");
            setError(null);
          }}
          className={clsx(
            "flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all cursor-pointer",
            toolMode === "quiz"
              ? "bg-subtle text-white border border-border-subtle shadow-subtle"
              : "text-text-muted hover:text-text-secondary",
          )}
        >
          <HelpCircle size={13} />
          <span>5-Q Quiz</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setToolMode("flashcards");
            setError(null);
          }}
          className={clsx(
            "flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all cursor-pointer",
            toolMode === "flashcards"
              ? "bg-subtle text-white border border-border-subtle shadow-subtle"
              : "text-text-muted hover:text-text-secondary",
          )}
        >
          <Layers size={13} />
          <span>Flashcards</span>
        </button>
      </div>

      {/* Tool Input Form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
        <label className="text-xs font-medium text-text-secondary">
          {toolMode === "quiz" ? "Quiz Topic" : "Flashcard Topic"}
        </label>
        <div className="relative">
          <input
            type="text"
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value);
              if (error) setError(null);
            }}
            disabled={loading || !sessionId}
            placeholder={
              toolMode === "quiz"
                ? "e.g. Chapter 3, Architecture, Algorithms…"
                : "e.g. Key Vocabulary, Core Mechanisms…"
            }
            className="w-full rounded-lg bg-canvas border border-border-subtle px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-border-strong transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          />
        </div>

        {/* Suggestion tags */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-mono text-text-muted">Preset:</span>
          {sampleTopics.map((tag) => (
            <button
              key={tag}
              type="button"
              disabled={loading || !sessionId}
              onClick={() => {
                setTopic(tag);
                if (error) setError(null);
              }}
              className="text-[10px] font-mono px-2 py-0.5 rounded bg-subtle border border-border-subtle text-text-secondary hover:text-white hover:border-border-strong transition-colors disabled:opacity-40 cursor-pointer"
            >
              {tag}
            </button>
          ))}
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-1.5 p-2 rounded-lg bg-subtle border border-red-500/40 text-red-400 text-xs">
            <span className="leading-tight">{error}</span>
          </div>
        )}

        {/* Generate Button */}
        <button
          type="submit"
          disabled={loading || !sessionId || !topic.trim()}
          className="flex items-center justify-center gap-2 mt-1 px-4 py-2.5 rounded-lg bg-white text-black hover:bg-neutral-200 active:scale-[0.98] text-xs font-medium shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          {loading ? (
            <>
              <Loader2 size={13} className="animate-spin text-black" />
              <span>Generating with Gemini…</span>
            </>
          ) : (
            <>
              <Sparkles size={13} />
              <span>
                {toolMode === "quiz" ? "Generate 5-Question Quiz" : "Generate Flashcards"}
              </span>
            </>
          )}
        </button>
      </form>

      {/* Info Card */}
      <div className="flex items-start gap-2.5 p-3 rounded-lg bg-subtle/50 border border-border-subtle text-text-muted text-xs">
        <Info size={14} className="shrink-0 text-text-secondary mt-0.5" />
        <div className="leading-relaxed">
          <span className="text-text-secondary font-medium block mb-0.5">
            Active Recall Protocol
          </span>
          {toolMode === "quiz"
            ? "Multiple-choice validation grounded strictly in your retrieved document chunks."
            : "High-yield prompt & explanation cards designed for spaced repetition."}
        </div>
      </div>
    </div>
  );
}
