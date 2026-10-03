// src/components/Chat/ChatWindow.tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquareDashed } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { PdfPreviewModal } from "./PdfPreviewModal";
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
  const [previewSource, setPreviewSource] = useState<Source | null>(null);
  const closePreview = useCallback(() => setPreviewSource(null), []);

  // Auto-scroll to bottom on new message / token
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full bg-canvas">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6 space-y-4 scroll-smooth">
        {messages.length === 0 ? (
          <EmptyState hasSession={!!activeSession} tutorMode={tutorMode} />
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={onCitationClick}
              onPreviewPage={setPreviewSource}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {previewSource && sessionId && (
        <PdfPreviewModal
          key={`${sessionId}:${previewSource.doc_id}`}
          sessionId={sessionId}
          source={previewSource}
          onClose={closePreview}
        />
      )}

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
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8 py-20">
      <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-subtle border border-border-subtle text-text-muted">
        <MessageSquareDashed size={20} />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-text-primary mb-1">
          {hasSession
            ? tutorMode
              ? "Socratic Session Active"
              : "Ask Anything About Your Notes"
            : "No Session Selected"}
        </h3>
        <p className="text-xs text-text-muted max-w-sm leading-relaxed">
          {hasSession
            ? tutorMode
              ? "Your tutor will guide you with targeted questions and hints to reinforce your understanding."
              : "Upload documents to the left pane and query concepts to get cited answers."
            : "Select or create a study session in the sidebar to begin."}
        </p>
      </div>
    </div>
  );
}
