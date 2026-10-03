// src/components/Sidebar/StudyTools.tsx
import { useState, type FormEvent } from "react";
import { Sparkles, Brain, Loader2, Lightbulb, AlertCircle, HelpCircle, Layers } from "lucide-react";
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
      setError("Please upload at least one study note or document first.");
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
        err?.message || `Failed to generate ${toolMode}. Make sure relevant notes are uploaded.`,
      );
    } finally {
      setLoading(false);
    }
  };

  const sampleTopics = ["Key Concepts", "Core Definitions", "Practice Exam"];

  return (
    <div className="flex flex-col gap-4">
      {/* Title */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-indigo-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Active Recall Tools
          </h3>
        </div>
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 border border-violet-500/30">
          Gemini AI
        </span>
      </div>

      {/* Mode Switcher */}
      <div className="grid grid-cols-2 p-1 rounded-xl bg-slate-950/70 border border-slate-800">
        <button
          type="button"
          onClick={() => {
            setToolMode("quiz");
            setError(null);
          }}
          className={clsx(
            "flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-medium transition-all cursor-pointer",
            toolMode === "quiz"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-slate-400 hover:text-slate-200",
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
            "flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-medium transition-all cursor-pointer",
            toolMode === "flashcards"
              ? "bg-violet-600 text-white shadow-sm"
              : "text-slate-400 hover:text-slate-200",
          )}
        >
          <Layers size={13} />
          <span>Flashcards</span>
        </button>
      </div>

      {/* Tool Input Form */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-2.5">
        <label className="text-xs font-medium text-slate-300">
          {toolMode === "quiz" ? "Quiz Me On..." : "Make Flashcards On..."}
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
                ? "e.g. Chapter 3, Photosynthesis, Algorithms..."
                : "e.g. Formulas, Key Vocabulary, Core Mechanisms..."
            }
            className="w-full rounded-xl bg-slate-800/90 border border-slate-700/80 px-3.5 py-2.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {/* Suggestion tags */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-slate-500">Quick:</span>
          {sampleTopics.map((tag) => (
            <button
              key={tag}
              type="button"
              disabled={loading || !sessionId}
              onClick={() => {
                setTopic(tag);
                if (error) setError(null);
              }}
              className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 hover:text-indigo-300 hover:bg-slate-700/80 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {tag}
            </button>
          ))}
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-1.5 p-2 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            <AlertCircle size={14} className="shrink-0 mt-0.5" />
            <span className="leading-tight">{error}</span>
          </div>
        )}

        {/* Generate Button */}
        <button
          type="submit"
          disabled={loading || !sessionId || !topic.trim()}
          className={clsx(
            "flex items-center justify-center gap-2 mt-1 px-4 py-2.5 rounded-xl text-white text-xs font-semibold shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer",
            toolMode === "quiz"
              ? "bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 shadow-indigo-600/20"
              : "bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 shadow-violet-600/20",
          )}
        >
          {loading ? (
            <>
              <Loader2 size={14} className="animate-spin text-white" />
              <span>
                {toolMode === "quiz"
                  ? "Analyzing Notes & Generating Quiz…"
                  : "Synthesizing Flashcard Deck…"}
              </span>
            </>
          ) : (
            <>
              <Sparkles size={14} />
              <span>
                {toolMode === "quiz"
                  ? "Generate 5-Question Quiz"
                  : "Generate Flashcard Deck"}
              </span>
            </>
          )}
        </button>
      </form>

      {/* Educational Study Note Card */}
      <div className="flex items-start gap-2.5 p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-slate-400 text-xs">
        <Lightbulb size={16} className="shrink-0 text-amber-400 mt-0.5" />
        <div className="leading-relaxed">
          <strong className="text-slate-300 font-medium block mb-0.5">
            Active Recall Technique
          </strong>
          {toolMode === "quiz"
            ? "Testing yourself before rereading notes boosts memory retention by over 50%. The quiz is grounded strictly in your notes."
            : "Flashcards test high-yield concepts and definitions. Flip the card to test whether you can recall before seeing the explanation."}
        </div>
      </div>
    </div>
  );
}

