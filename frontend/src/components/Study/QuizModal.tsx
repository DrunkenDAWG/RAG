// src/components/Study/QuizModal.tsx
import { useState } from "react";
import { CheckCircle2, XCircle, Lightbulb, Trophy, RotateCcw, X, HelpCircle, ArrowRight } from "lucide-react";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <HelpCircle size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase tracking-wider font-bold text-indigo-400">
                  Active Recall Quiz
                </span>
                <span className="text-xs text-slate-500">•</span>
                <span className="text-xs text-slate-400 font-medium truncate max-w-xs">
                  {topic}
                </span>
              </div>
              {!isFinished && (
                <p className="text-xs text-slate-500 mt-0.5">
                  Question {currentIndex + 1} of {questions.length}
                </p>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            title="Close Quiz"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {!isFinished ? (
            <div className="flex flex-col gap-6">
              {/* Progress bar */}
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-300"
                  style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
                />
              </div>

              {/* Question Text */}
              <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
                <h3 className="text-base sm:text-lg font-semibold text-slate-100 leading-snug">
                  {currentQuestion.question}
                </h3>
              </div>

              {/* Options */}
              <div className="flex flex-col gap-2.5">
                {currentQuestion.options.map((option, idx) => {
                  const isSelected = selectedOption === option;
                  const isCorrect = option === currentQuestion.correct_answer;
                  let optionStyles = "bg-slate-800/60 border-slate-700/80 hover:bg-slate-800 hover:border-indigo-500/50 text-slate-200";

                  if (isAnswerSubmitted) {
                    if (isCorrect) {
                      optionStyles = "bg-emerald-500/15 border-emerald-500/80 text-emerald-100";
                    } else if (isSelected) {
                      optionStyles = "bg-rose-500/15 border-rose-500/80 text-rose-100";
                    } else {
                      optionStyles = "bg-slate-800/30 border-slate-700/40 text-slate-500 opacity-60";
                    }
                  }

                  return (
                    <button
                      key={idx}
                      disabled={isAnswerSubmitted}
                      onClick={() => handleSelectOption(option)}
                      className={clsx(
                        "group flex items-start gap-3.5 p-3.5 rounded-xl border text-left text-sm transition-all duration-150",
                        optionStyles,
                        !isAnswerSubmitted && "cursor-pointer active:scale-[0.99]",
                      )}
                    >
                      <span
                        className={clsx(
                          "shrink-0 flex items-center justify-center w-6 h-6 rounded-lg text-xs font-bold transition-colors",
                          isAnswerSubmitted && isCorrect
                            ? "bg-emerald-500 text-white"
                            : isAnswerSubmitted && isSelected
                            ? "bg-rose-500 text-white"
                            : "bg-slate-700/60 text-slate-300 group-hover:bg-indigo-600 group-hover:text-white",
                        )}
                      >
                        {optionLabels[idx] ?? idx + 1}
                      </span>
                      <span className="flex-1 mt-0.5 leading-snug">{option}</span>
                      {isAnswerSubmitted && isCorrect && (
                        <CheckCircle2 size={18} className="shrink-0 text-emerald-400 mt-0.5" />
                      )}
                      {isAnswerSubmitted && isSelected && !isCorrect && (
                        <XCircle size={18} className="shrink-0 text-rose-400 mt-0.5" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Explanation box */}
              {isAnswerSubmitted && (
                <div className="flex gap-3 p-4 rounded-xl bg-slate-800/60 border border-slate-700/70 animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="shrink-0 mt-0.5 text-amber-400">
                    <Lightbulb size={18} />
                  </div>
                  <div className="flex-1 text-xs sm:text-sm">
                    <p className="font-semibold text-slate-200 mb-1">Concept Explanation</p>
                    <p className="text-slate-400 leading-relaxed">
                      {currentQuestion.explanation}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Results Screen */
            <div className="flex flex-col items-center justify-center text-center py-8 gap-5">
              <div className="flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-tr from-amber-500/20 to-yellow-500/20 border border-amber-500/30 text-amber-400">
                <Trophy size={40} />
              </div>

              <div>
                <h3 className="text-xl font-bold text-white mb-1">Quiz Completed!</h3>
                <p className="text-sm text-slate-400">
                  Topic: <strong className="text-slate-200">{topic}</strong>
                </p>
              </div>

              <div className="flex items-center gap-6 px-6 py-4 rounded-2xl bg-slate-800/60 border border-slate-700/80">
                <div className="text-center">
                  <p className="text-2xl font-black text-indigo-400">
                    {calculateScore()} / {questions.length}
                  </p>
                  <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold mt-0.5">
                    Score
                  </p>
                </div>
                <div className="w-px h-8 bg-slate-700" />
                <div className="text-center">
                  <p className="text-2xl font-black text-emerald-400">
                    {Math.round((calculateScore() / questions.length) * 100)}%
                  </p>
                  <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold mt-0.5">
                    Accuracy
                  </p>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-400 max-w-md">
                {calculateScore() === questions.length
                  ? "🔥 Perfect score! You have thoroughly mastered these notes."
                  : calculateScore() >= questions.length / 2
                  ? "👍 Great effort! Review the explanations above to solidify any weak points."
                  : "💡 Keep practicing! Ask your Socratic Tutor to explain the difficult parts."}
              </p>

              <div className="flex items-center gap-3 mt-4">
                <button
                  onClick={handleRestart}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-medium text-slate-200 transition-colors"
                >
                  <RotateCcw size={15} />
                  Retake Quiz
                </button>
                <button
                  onClick={onClose}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold text-white transition-colors"
                >
                  Return to Study Hub
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!isFinished && (
          <div className="flex items-center justify-between px-6 py-3.5 border-t border-slate-800 bg-slate-900/90">
            <span className="text-xs text-slate-500">
              {isAnswerSubmitted
                ? selectedOption === currentQuestion.correct_answer
                  ? "✅ Correct answer!"
                  : "❌ Incorrect answer"
                : "Select an option to check your knowledge"}
            </span>

            {isAnswerSubmitted && (
              <button
                onClick={handleNext}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-semibold transition-colors"
              >
                {currentIndex < questions.length - 1 ? (
                  <>
                    Next Question <ArrowRight size={15} />
                  </>
                ) : (
                  <>
                    Finish & View Score <Trophy size={15} />
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
