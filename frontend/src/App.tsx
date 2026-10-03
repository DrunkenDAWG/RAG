// src/App.tsx
import { useEffect, useState, useRef } from "react";
import { GraduationCap, BookOpen, Brain } from "lucide-react";
import clsx from "clsx";
import { useSession } from "./hooks/useSession";
import { useDocuments } from "./hooks/useDocuments";
import { SessionSwitcher } from "./components/Sidebar/SessionSwitcher";
import { DocumentUpload } from "./components/Sidebar/DocumentUpload";
import { DocumentList } from "./components/Sidebar/DocumentList";
import { StudyTools } from "./components/Sidebar/StudyTools";
import { QuizModal } from "./components/Study/QuizModal";
import { FlashcardModal } from "./components/Study/FlashcardModal";
import { ChatWindow } from "./components/Chat/ChatWindow";
import type { FlashcardDeck, Quiz, Source } from "./types";

export default function App() {
  const {
    sessions,
    activeSession,
    activeId,
    loading: sessionLoading,
    newSession,
    removeSession,
    renameSession,
    setActiveId,
  } = useSession();

  // Auto-create a session on first visit
  useEffect(() => {
    if (sessions.length === 0) newSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const {
    documents,
    uploads,
    loading: docLoading,
    upload,
    remove,
  } = useDocuments(activeId);

  // Left Pane tab state
  const [activeTab, setActiveTab] = useState<"documents" | "tools">("documents");

  // Quiz active overlay state
  const [activeQuiz, setActiveQuiz] = useState<Quiz | null>(null);
  const [quizTopic, setQuizTopic] = useState<string>("");

  // Flashcards active overlay state
  const [activeDeck, setActiveDeck] = useState<FlashcardDeck | null>(null);
  const [deckTopic, setDeckTopic] = useState<string>("");

  // Citation document highlighting
  const [highlightedDocId, setHighlightedDocId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleCitationClick = (source: Source) => {
    // Switch to documents tab in Left Pane so student immediately sees the cited doc
    setActiveTab("documents");
    setHighlightedDocId(source.doc_id || source.filename);

    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current);
    }
    highlightTimeoutRef.current = setTimeout(() => {
      setHighlightedDocId(null);
    }, 4500);
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* ── Left Pane: Knowledge Base & Study Tools ───────────────────────── */}
      <aside className="flex flex-col w-80 lg:w-96 shrink-0 border-r border-slate-700/60 bg-slate-900/90 backdrop-blur z-20">
        {/* Hub Branding */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-700/60 bg-slate-900">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 shadow-md shadow-indigo-600/30">
            <GraduationCap size={18} className="text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="text-sm font-bold tracking-tight text-white">Student Study Hub</h1>
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                AI Tutor
              </span>
            </div>
            <p className="text-xs text-slate-400">Knowledge Base & Active Recall</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex p-2 bg-slate-950/60 border-b border-slate-800">
          <button
            onClick={() => setActiveTab("documents")}
            className={clsx(
              "flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer",
              activeTab === "documents"
                ? "bg-slate-800 text-indigo-300 shadow border border-slate-700/80"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50",
            )}
          >
            <BookOpen size={14} />
            <span>Notes & Docs</span>
            {documents.length > 0 && (
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-slate-700 text-slate-300">
                {documents.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("tools")}
            className={clsx(
              "flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer",
              activeTab === "tools"
                ? "bg-slate-800 text-indigo-300 shadow border border-slate-700/80"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/50",
            )}
          >
            <Brain size={14} className="text-indigo-400" />
            <span>Study Tools</span>
          </button>
        </div>

        {/* Left Pane Tab Body */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-5 p-4">
          {activeTab === "documents" ? (
            <>
              {/* Study Session Switcher */}
              <SessionSwitcher
                sessions={sessions}
                activeId={activeId}
                loading={sessionLoading}
                onSelect={setActiveId}
                onCreate={newSession}
                onDelete={removeSession}
                onRename={renameSession}
              />

              {/* Uploads and Document list */}
              <div className="border-t border-slate-700/40 pt-4 flex flex-col gap-4">
                <DocumentUpload
                  uploads={uploads}
                  disabled={!activeId}
                  onUpload={upload}
                />
                <DocumentList
                  documents={documents}
                  loading={docLoading}
                  onDelete={remove}
                  highlightedDocId={highlightedDocId}
                />
              </div>
            </>
          ) : (
            /* Study Tools Tab */
            <StudyTools
              sessionId={activeId}
              documentCount={documents.length}
              onQuizGenerated={(quiz, topic) => {
                setActiveQuiz(quiz);
                setQuizTopic(topic);
              }}
              onFlashcardsGenerated={(deck, topic) => {
                setActiveDeck(deck);
                setDeckTopic(topic);
              }}
            />
          )}
        </div>

        {/* Sidebar footer status */}
        <div className="px-4 py-3 border-t border-slate-800 bg-slate-900/60 text-xs text-slate-500 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Study Companion Online
          </span>
          <span className="text-[11px] text-slate-600">Groq (Chat) • Gemini (Recall)</span>
        </div>
      </aside>

      {/* ── Right Pane: Socratic Tutor Chat ───────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <ChatWindow
          activeSession={activeSession}
          onCitationClick={handleCitationClick}
        />

        {/* Interactive Active Recall Quiz Modal Overlay */}
        {activeQuiz && (
          <QuizModal
            quiz={activeQuiz}
            topic={quizTopic}
            onClose={() => setActiveQuiz(null)}
          />
        )}

        {/* Interactive Active Recall Flashcard Modal Overlay */}
        {activeDeck && (
          <FlashcardModal
            deck={activeDeck}
            topic={deckTopic}
            onClose={() => setActiveDeck(null)}
          />
        )}
      </main>
    </div>
  );
}

