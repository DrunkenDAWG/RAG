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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/80 backdrop-blur-md animate-in fade-in duration-150">
      <div className="relative w-full max-w-xl bg-surface border border-border-strong rounded-xl shadow-modal flex flex-col overflow-hidden max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle bg-surface">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-md bg-subtle border border-border-subtle text-text-secondary">
              <Layers size={15} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-primary tracking-tight">
                  Active Recall Flashcards
                </span>
                <span className="text-xs text-text-muted">•</span>
                <span className="text-xs font-mono text-text-muted truncate max-w-xs">
                  {topic}
                </span>
              </div>
              <p className="text-[11px] font-mono text-text-muted mt-0.5">
                Card {currentIndex + 1} of {cards.length} ({masteredIds.size} mastered)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleShuffle}
              className="p-1.5 text-text-muted hover:text-text-primary rounded-md hover:bg-subtle transition-colors cursor-pointer"
              title="Shuffle Cards"
            >
              <Shuffle size={14} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-text-muted hover:text-text-primary rounded-md hover:bg-subtle transition-colors cursor-pointer"
              title="Close Flashcards (Esc)"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-1 bg-canvas border-b border-border-subtle">
          <div
            className="h-full bg-white transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / cards.length) * 100}%` }}
          />
        </div>

        {/* Card Viewport */}
        <div className="flex-1 p-6 flex flex-col items-center justify-center min-h-[300px]">
          <div
            onClick={() => setIsFlipped((prev) => !prev)}
            className="relative w-full h-64 cursor-pointer select-none group"
          >
            <div
              className={clsx(
                "w-full h-full duration-300 rounded-xl p-6 flex flex-col justify-between transition-all shadow-subtle border",
                isFlipped
                  ? "bg-canvas border-border-strong text-text-primary"
                  : "bg-subtle/80 border-border-subtle group-hover:border-border-strong text-text-primary",
              )}
            >
              {/* Card Header badge */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-canvas text-text-secondary border border-border-subtle">
                  {currentCard.key_term || "Concept"}
                </span>

                <div className="flex items-center gap-1 text-text-muted text-[11px] font-mono">
                  <RotateCw size={11} className="group-hover:rotate-180 transition-transform duration-300" />
                  <span>{isFlipped ? "Answer" : "Click / Space to Flip"}</span>
                </div>
              </div>

              {/* Main Content */}
              <div className="my-auto text-center px-4">
                {!isFlipped ? (
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted block mb-2">
                      Prompt
                    </span>
                    <h3 className="text-sm sm:text-base font-semibold text-text-primary leading-snug">
                      {currentCard.front}
                    </h3>
                  </div>
                ) : (
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted block mb-2">
                      Explanation
                    </span>
                    <p className="text-xs sm:text-sm text-text-primary leading-relaxed font-normal">
                      {currentCard.back}
                    </p>
                  </div>
                )}
              </div>

              {/* Card Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-border-subtle text-[10px] font-mono text-text-muted">
                <span>Side {isFlipped ? "2 of 2" : "1 of 2"}</span>
                <span className="flex items-center gap-1">
                  <BookOpen size={11} /> Grounded Notes
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Controls Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-border-subtle bg-surface">
          <button
            onClick={toggleMastered}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer",
              isMastered
                ? "bg-white text-black border-white"
                : "bg-subtle border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-strong",
            )}
          >
            <CheckCircle2 size={13} className={isMastered ? "text-black" : "text-text-muted"} />
            <span>{isMastered ? "Mastered" : "Mark Mastered"}</span>
          </button>

          <div className="flex items-center gap-2 font-mono">
            <button
              onClick={handlePrev}
              className="p-1.5 rounded-lg bg-subtle hover:bg-canvas border border-border-subtle hover:border-border-strong text-text-secondary hover:text-white transition-colors cursor-pointer"
              title="Previous (Left Arrow)"
            >
              <ChevronLeft size={14} />
            </button>

            <span className="text-xs text-text-muted px-1.5">
              {currentIndex + 1} / {cards.length}
            </span>

            <button
              onClick={handleNext}
              className="p-1.5 rounded-lg bg-white text-black hover:bg-neutral-200 transition-colors cursor-pointer font-medium"
              title="Next (Right Arrow)"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
