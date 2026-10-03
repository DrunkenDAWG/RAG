// src/components/Chat/ChatWindow.tsx
import { useEffect, useRef, useState } from "react";
import { Bot, MessageSquareDashed, GraduationCap } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { useChat } from "../../hooks/useChat";
import type { Session, Source } from "../../types";

interface Props {
  activeSession: Session | null;
  onCitationClick?: (source: Source) => void;
}

export function ChatWindow({ activeSession, onCitationClick }: Props) {
  const sessionId = activeSession?.session_id ?? null;
  const [tutorMode, setTutorMode] = useState(false);
  const { messages, isStreaming, sendMessage, stopStreaming } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new message / token
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-700/60 bg-slate-900/60 backdrop-blur">
        <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30">
          <Bot size={16} className="text-indigo-400" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100">
              {activeSession ? activeSession.label : "Student Study Hub"}
            </h2>
            {tutorMode && (
              <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-600/20 text-violet-300 border border-violet-500/30">
                <GraduationCap size={11} /> Socratic Tutor Active
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            {activeSession
              ? `${activeSession.session_id.slice(0, 8)}…`
              : "Select a session to begin"}
          </p>
        </div>
        {isStreaming && (
          <div className="ml-auto flex items-center gap-1.5 text-xs text-indigo-400">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            Generating…
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-4 space-y-2 scroll-smooth">
        {messages.length === 0 ? (
          <EmptyState hasSession={!!activeSession} tutorMode={tutorMode} />
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={onCitationClick}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        isStreaming={isStreaming}
        disabled={!activeSession}
        tutorMode={tutorMode}
        onToggleTutorMode={setTutorMode}
        onSend={(query) => sendMessage(query, tutorMode)}
        onStop={stopStreaming}
      />
    </div>
  );
}

function EmptyState({
  hasSession,
  tutorMode,
}: {
  hasSession: boolean;
  tutorMode?: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-8 py-16">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700">
        <MessageSquareDashed size={28} className="text-indigo-400" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-slate-200 mb-1">
          {hasSession
            ? tutorMode
              ? "Socratic Study Session Ready"
              : "Ask Anything About Your Notes"
            : "No study session selected"}
        </h3>
        <p className="text-sm text-slate-400 max-w-sm">
          {hasSession
            ? tutorMode
              ? "Tutor mode is active. Your study companion will guide you through concepts using questions and hints instead of giving away immediate answers."
              : "Upload PDFs or study notes on the left, then ask questions to get grounded answers with clickable citations."
            : "Create or select a study session from the left sidebar to get started."}
        </p>
      </div>
    </div>
  );
}
