// src/components/Study/QuizModal.tsx
import { useState } from "react";
import { CheckCircle2, XCircle, Trophy, RotateCcw, X, HelpCircle, ArrowRight, BookOpen } from "lucide-react";
import clsx from "clsx";
import type { Quiz } from "../../types";

interface Props {
  quiz: Quiz;
  topic: string;
  onClose: () => void;
}

export function QuizModal({ quiz, topic, onClose }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isAnswerSubmitted, setIsAnswerSubmitted] = useState(false);
  const [userAnswers, setUserAnswers] = useState<{ [qIdx: number]: string }>({});
  const [isFinished, setIsFinished] = useState(false);

  const questions = quiz.questions || [];
  const currentQuestion = questions[currentIndex];

  const handleSelectOption = (option: string) => {
    if (isAnswerSubmitted) return;
    setSelectedOption(option);
    setIsAnswerSubmitted(true);
    setUserAnswers((prev) => ({ ...prev, [currentIndex]: option }));
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      const nextAnswer = userAnswers[currentIndex + 1] ?? null;
      setSelectedOption(nextAnswer);
      setIsAnswerSubmitted(nextAnswer !== null);
    } else {
      setIsFinished(true);
    }
  };

  const handleRestart = () => {
    setCurrentIndex(0);
    setSelectedOption(null);
    setIsAnswerSubmitted(false);
    setUserAnswers({});
    setIsFinished(false);
  };

  const calculateScore = () => {
    return questions.reduce((score, q, idx) => {
      return userAnswers[idx] === q.correct_answer ? score + 1 : score;
    }, 0);
  };

  const optionLabels = ["A", "B", "C", "D"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/80 backdrop-blur-md animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-surface border border-border-strong rounded-xl shadow-modal flex flex-col overflow-hidden max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-subtle bg-surface">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-md bg-subtle border border-border-subtle text-text-secondary">
              <HelpCircle size={15} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text-primary tracking-tight">
                  Active Recall Quiz
                </span>
                <span className="text-xs text-text-muted">•</span>
                <span className="text-xs font-mono text-text-muted truncate max-w-xs">
                  {topic}
                </span>
              </div>
              {!isFinished && (
                <p className="text-[11px] font-mono text-text-muted mt-0.5">
                  Question {currentIndex + 1} of {questions.length}
                </p>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary rounded-md hover:bg-subtle transition-colors cursor-pointer"
            title="Close Quiz"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {!isFinished ? (
            <div className="flex flex-col gap-5">
              {/* Progress bar */}
              <div className="w-full h-1 bg-canvas border border-border-subtle rounded-full overflow-hidden">
                <div
                  className="h-full bg-white transition-all duration-300"
                  style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
                />
              </div>

              {/* Question Text */}
              <div className="p-4 rounded-lg bg-subtle/40 border border-border-subtle">
                <h3 className="text-sm sm:text-base font-semibold text-text-primary leading-snug">
                  {currentQuestion.question}
                </h3>
              </div>

              {/* Options */}
              <div className="flex flex-col gap-2">
                {currentQuestion.options.map((option, idx) => {
                  const isSelected = selectedOption === option;
                  const isCorrect = option === currentQuestion.correct_answer;
                  let optionStyles = "bg-subtle/50 border-border-subtle hover:border-border-strong text-text-primary";

                  if (isAnswerSubmitted) {
                    if (isCorrect) {
                      optionStyles = "bg-subtle border-emerald-500/70 text-emerald-300";
                    } else if (isSelected) {
                      optionStyles = "bg-subtle border-red-500/70 text-red-300";
                    } else {
                      optionStyles = "bg-subtle/20 border-border-subtle text-text-muted opacity-40";
                    }
                  }

                  return (
                    <button
                      key={idx}
                      disabled={isAnswerSubmitted}
                      onClick={() => handleSelectOption(option)}
                      className={clsx(
                        "group flex items-start gap-3 p-3 rounded-lg border text-left text-xs sm:text-sm transition-all",
                        optionStyles,
                        !isAnswerSubmitted && "cursor-pointer active:scale-[0.99]",
                      )}
                    >
                      <span
                        className={clsx(
                          "shrink-0 flex items-center justify-center w-5 h-5 rounded font-mono text-[11px] transition-colors",
                          isAnswerSubmitted && isCorrect
                            ? "bg-emerald-500 text-black font-semibold"
                            : isAnswerSubmitted && isSelected
                            ? "bg-red-500 text-white font-semibold"
                            : "bg-canvas border border-border-subtle text-text-muted group-hover:text-text-primary",
                        )}
                      >
                        {optionLabels[idx] ?? idx + 1}
                      </span>
                      <span className="flex-1 mt-0.5 leading-snug">{option}</span>
                      {isAnswerSubmitted && isCorrect && (
                        <CheckCircle2 size={16} className="shrink-0 text-emerald-400 mt-0.5" />
                      )}
                      {isAnswerSubmitted && isSelected && !isCorrect && (
                        <XCircle size={16} className="shrink-0 text-red-400 mt-0.5" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Explanation box */}
              {isAnswerSubmitted && (
                <div className="flex gap-3 p-3.5 rounded-lg bg-subtle/60 border border-border-subtle text-xs animate-in fade-in duration-150">
                  <BookOpen size={15} className="shrink-0 text-text-secondary mt-0.5" />
                  <div className="flex-1 leading-relaxed">
                    <p className="font-medium text-text-primary mb-0.5">Explanation</p>
                    <p className="text-text-muted leading-relaxed">
                      {currentQuestion.explanation}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Results Screen */
            <div className="flex flex-col items-center justify-center text-center py-8 gap-4">
              <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-subtle border border-border-subtle text-text-primary">
                <Trophy size={28} />
              </div>

              <div>
                <h3 className="text-base font-semibold text-text-primary mb-1">Assessment Complete</h3>
                <p className="text-xs font-mono text-text-muted">
                  Topic: {topic}
                </p>
              </div>

              <div className="flex items-center gap-6 px-6 py-3.5 rounded-lg bg-subtle border border-border-subtle">
                <div className="text-center font-mono">
                  <p className="text-xl font-bold text-text-primary">
                    {calculateScore()} / {questions.length}
                  </p>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted mt-0.5">
                    Score
                  </p>
                </div>
                <div className="w-px h-7 bg-border-subtle" />
                <div className="text-center font-mono">
                  <p className="text-xl font-bold text-text-primary">
                    {Math.round((calculateScore() / questions.length) * 100)}%
                  </p>
                  <p className="text-[10px] uppercase tracking-wider text-text-muted mt-0.5">
                    Accuracy
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5 mt-3">
                <button
                  onClick={handleRestart}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-subtle hover:bg-canvas border border-border-subtle text-xs font-medium text-text-primary transition-all cursor-pointer"
                >
                  <RotateCcw size={13} />
                  Retake
                </button>
                <button
                  onClick={onClose}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white text-black hover:bg-neutral-200 text-xs font-medium transition-all cursor-pointer"
                >
                  Return to Hub
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!isFinished && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-border-subtle bg-surface">
            <span className="text-xs text-text-muted font-mono">
              {isAnswerSubmitted
                ? selectedOption === currentQuestion.correct_answer
                  ? "✓ Correct"
                  : "✗ Incorrect"
                : "Select an answer choice"}
            </span>

            {isAnswerSubmitted && (
              <button
                onClick={handleNext}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white text-black hover:bg-neutral-200 text-xs font-medium transition-all cursor-pointer"
              >
                {currentIndex < questions.length - 1 ? (
                  <>
                    Next Question <ArrowRight size={13} />
                  </>
                ) : (
                  <>
                    View Results <Trophy size={13} />
                  </>
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
