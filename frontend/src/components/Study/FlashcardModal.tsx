// src/components/Study/FlashcardModal.tsx
import { useState, useEffect } from "react";
import {
  Layers,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  Shuffle,
  X,
  BookOpen,
  CheckCircle2,
} from "lucide-react";
import clsx from "clsx";
import type { FlashcardDeck } from "../../types";

interface Props {
  deck: FlashcardDeck;
  topic: string;
  onClose: () => void;
}

export function FlashcardModal({ deck, topic, onClose }: Props) {
  const [cards, setCards] = useState(deck.cards || []);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [masteredIds, setMasteredIds] = useState<Set<number>>(new Set());

  const currentCard = cards[currentIndex];

  // Keyboard navigation: Space to flip, Arrows to navigate, Esc to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        handlePrev();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, cards.length]);

  const handleNext = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev < cards.length - 1 ? prev + 1 : 0));
  };

  const handlePrev = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : cards.length - 1));
  };

  const handleShuffle = () => {
    setIsFlipped(false);
    setCards((prev) => [...prev].sort(() => Math.random() - 0.5));
    setCurrentIndex(0);
  };

  const toggleMastered = () => {
    setMasteredIds((prev) => {
      const next = new Set(prev);
      if (next.has(currentIndex)) {
        next.delete(currentIndex);
      } else {
        next.add(currentIndex);
      }
      return next;
    });
  };

  if (!currentCard) return null;

  const isMastered = masteredIds.has(currentIndex);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/95">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-violet-600/20 text-violet-400 border border-violet-500/30">
              <Layers size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase tracking-wider font-bold text-violet-400">
                  Active Recall Flashcards
                </span>
                <span className="text-xs text-slate-500">•</span>
                <span className="text-xs text-slate-400 font-medium truncate max-w-xs">
                  {topic}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Card {currentIndex + 1} of {cards.length} ({masteredIds.size} mastered)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleShuffle}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
              title="Shuffle Cards"
            >
              <Shuffle size={16} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
              title="Close Flashcards (Esc)"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-1 bg-slate-800">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / cards.length) * 100}%` }}
          />
        </div>

        {/* Card Viewport */}
        <div className="flex-1 p-6 flex flex-col items-center justify-center min-h-[320px]">
          <div
            onClick={() => setIsFlipped((prev) => !prev)}
            className="relative w-full h-72 cursor-pointer select-none group perspective-1000"
          >
            <div
              className={clsx(
                "w-full h-full duration-500 rounded-2xl p-6 flex flex-col justify-between transition-transform transform-style-3d shadow-xl border",
                isFlipped
                  ? "bg-gradient-to-br from-slate-900 via-indigo-950/40 to-slate-900 border-indigo-500/50"
                  : "bg-gradient-to-br from-slate-800/90 via-slate-800/60 to-slate-900 border-slate-700/80 group-hover:border-violet-500/50",
              )}
            >
              {/* Card Header badge */}
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold tracking-wider uppercase px-2.5 py-1 rounded-full bg-slate-700/60 text-violet-300 border border-violet-500/30">
                  {currentCard.key_term || "Concept"}
                </span>

                <div className="flex items-center gap-1.5 text-slate-400 text-xs">
                  <RotateCw size={13} className="text-violet-400 group-hover:rotate-180 transition-transform duration-500" />
                  <span className="text-[11px]">
                    {isFlipped ? "Showing Answer" : "Click / Space to Flip"}
                  </span>
                </div>
              </div>

              {/* Main Content */}
              <div className="my-auto text-center px-4">
                {!isFlipped ? (
                  <div>
                    <span className="text-xs uppercase tracking-wider text-slate-500 font-bold block mb-2">
                      Prompt / Question
                    </span>
                    <h3 className="text-base sm:text-lg font-semibold text-slate-100 leading-snug">
                      {currentCard.front}
                    </h3>
                  </div>
                ) : (
                  <div>
                    <span className="text-xs uppercase tracking-wider text-emerald-400 font-bold block mb-2">
                      Key Takeaway / Explanation
                    </span>
                    <p className="text-sm sm:text-base text-slate-200 leading-relaxed font-normal">
                      {currentCard.back}
                    </p>
                  </div>
                )}
              </div>

              {/* Card Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-700/40 text-[11px] text-slate-500">
                <span>Side {isFlipped ? "2 of 2" : "1 of 2"}</span>
                <span className="flex items-center gap-1 text-slate-400">
                  <BookOpen size={12} /> Grounded in Notes
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Controls Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMastered}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors cursor-pointer",
                isMastered
                  ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                  : "bg-slate-800/70 border-slate-700 text-slate-400 hover:text-slate-200",
              )}
            >
              <CheckCircle2 size={14} className={isMastered ? "text-emerald-400" : "text-slate-500"} />
              <span>{isMastered ? "Mastered" : "Mark Mastered"}</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handlePrev}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition-colors cursor-pointer"
              title="Previous Card (Left Arrow)"
            >
              <ChevronLeft size={16} />
            </button>

            <span className="text-xs font-semibold text-slate-400 px-2">
              {currentIndex + 1} / {cards.length}
            </span>

            <button
              onClick={handleNext}
              className="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer"
              title="Next Card (Right Arrow)"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
