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
    <div className="flex h-screen bg-canvas bg-grid-dots text-text-primary font-sans overflow-hidden antialiased">
      {/* ── Left Pane: Knowledge Base & Study Tools ───────────────────────── */}
      <aside className="flex flex-col w-80 lg:w-96 shrink-0 border-r border-border-subtle bg-surface/95 backdrop-blur-md z-20">
        {/* Hub Branding */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border-subtle bg-surface">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-subtle border border-border-subtle text-white">
            <GraduationCap size={16} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold tracking-tight text-white">Study Hub</h1>
              <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-subtle text-text-secondary border border-border-subtle">
                v1.0
              </span>
            </div>
            <p className="text-xs text-text-muted">RAG Knowledge Base & Active Recall</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex p-2 bg-canvas/40 border-b border-border-subtle gap-1">
          <button
            onClick={() => setActiveTab("documents")}
            className={clsx(
              "flex-1 flex items-center justify-center gap-2 py-1.5 px-3 rounded-md text-xs font-medium transition-colors cursor-pointer",
              activeTab === "documents"
                ? "bg-subtle text-white border border-border-subtle shadow-sm"
                : "text-text-muted hover:text-text-secondary hover:bg-subtle/50",
            )}
          >
            <BookOpen size={13} />
            <span>Documents</span>
            {documents.length > 0 && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-canvas text-text-secondary border border-border-subtle">
                {documents.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("tools")}
            className={clsx(
              "flex-1 flex items-center justify-center gap-2 py-1.5 px-3 rounded-md text-xs font-medium transition-colors cursor-pointer",
              activeTab === "tools"
                ? "bg-subtle text-white border border-border-subtle shadow-sm"
                : "text-text-muted hover:text-text-secondary hover:bg-subtle/50",
            )}
          >
            <Brain size={13} />
            <span>Study Tools</span>
          </button>
        </div>

        {/* Left Pane Tab Body */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-4 p-4">
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
              <div className="border-t border-border-subtle pt-4 flex flex-col gap-4">
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
        <div className="px-4 py-3 border-t border-border-subtle bg-surface text-xs text-text-muted flex items-center justify-between font-mono">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span className="text-[11px] text-text-secondary">Connected</span>
          </span>
          <span className="text-[10px] text-text-muted">Groq • Gemini • BGE</span>
        </div>
      </aside>

      {/* ── Right Pane: Socratic Tutor Chat ───────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden relative bg-canvas">
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
