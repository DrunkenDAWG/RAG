// src/components/Chat/ChatWindow.tsx
import { useEffect, useRef } from "react";
import { Bot, MessageSquareDashed } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { useChat } from "../../hooks/useChat";
import type { Session } from "../../types";

interface Props {
  activeSession: Session | null;
}

export function ChatWindow({ activeSession }: Props) {
  const sessionId = activeSession?.session_id ?? null;
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
          <h2 className="text-sm font-semibold text-slate-100">
            {activeSession ? activeSession.label : "RAG Assistant"}
          </h2>
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
          <EmptyState hasSession={!!activeSession} />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        isStreaming={isStreaming}
        disabled={!activeSession}
        onSend={sendMessage}
        onStop={stopStreaming}
      />
    </div>
  );
}

function EmptyState({ hasSession }: { hasSession: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-8 py-16">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700">
        <MessageSquareDashed size={28} className="text-slate-500" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-slate-300 mb-1">
          {hasSession ? "Start a conversation" : "No session selected"}
        </h3>
        <p className="text-sm text-slate-500 max-w-xs">
          {hasSession
            ? "Upload documents in the sidebar, then ask anything about their content."
            : "Create or select a session from the left sidebar to get started."}
        </p>
      </div>
    </div>
  );
}
