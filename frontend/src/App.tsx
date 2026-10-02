// src/App.tsx
import { useEffect } from "react";
import { Bot } from "lucide-react";
import { useSession } from "./hooks/useSession";
import { useDocuments } from "./hooks/useDocuments";
import { SessionSwitcher } from "./components/Sidebar/SessionSwitcher";
import { DocumentUpload } from "./components/Sidebar/DocumentUpload";
import { DocumentList } from "./components/Sidebar/DocumentList";
import { ChatWindow } from "./components/Chat/ChatWindow";

export default function App() {
  const {
    sessions, activeSession, activeId, loading: sessionLoading,
    newSession, removeSession, renameSession, setActiveId,
  } = useSession();

  // Auto-create a session on first visit
  useEffect(() => {
    if (sessions.length === 0) newSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const {
    documents, uploads, loading: docLoading, upload, remove,
  } = useDocuments(activeId);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* ── Left Sidebar ─────────────────────────────────────────────────── */}
      <aside className="flex flex-col w-72 shrink-0 border-r border-slate-700/60 bg-slate-900/80 backdrop-blur">
        {/* Branding */}
        <div className="flex items-center gap-2.5 px-5 py-5 border-b border-slate-700/60">
          <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-indigo-600">
            <Bot size={16} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white">LocalHost RAG</h1>
            <p className="text-xs text-slate-400">Document AI Assistant</p>
          </div>
        </div>

        {/* Scrollable sidebar body */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-5 p-4">
          <SessionSwitcher
            sessions={sessions}
            activeId={activeId}
            loading={sessionLoading}
            onSelect={setActiveId}
            onCreate={newSession}
            onDelete={removeSession}
            onRename={renameSession}
          />

          <div className="border-t border-slate-700/40 pt-4 flex flex-col gap-3">
            <DocumentUpload
              uploads={uploads}
              disabled={!activeId}
              onUpload={upload}
            />
            <DocumentList
              documents={documents}
              loading={docLoading}
              onDelete={remove}
            />
          </div>
        </div>

        {/* Sidebar footer */}
        <div className="px-4 py-3 border-t border-slate-700/40 text-xs text-slate-600">
          FastAPI · ChromaDB · Groq
        </div>
      </aside>

      {/* ── Main chat area ────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow activeSession={activeSession} />
      </main>
    </div>
  );
}
