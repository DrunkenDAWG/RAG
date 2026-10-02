// src/components/Chat/MessageBubble.tsx
// Renders a single chat message with Markdown, citation badges, and streaming cursor.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { Bot, User, Sparkles } from "lucide-react";
import { CitationBadge } from "./CitationPopover";
import type { Message } from "../../types";

interface Props {
  message: Message;
}

// Inject citation badges after numeric references like [1], [1,2]
function renderContentWithCitations(message: Message) {
  const { content, citations, isStreaming } = message;
  if (citations.length === 0) {
    return (
      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        {isStreaming && <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 rounded-sm" />}
      </div>
    );
  }

  // Split content around citation references and inject badge components
  const parts: (string | JSX.Element)[] = [];
  let remaining = content;
  let key = 0;

  const sorted = [...citations].sort((a, b) =>
    content.indexOf(`[${a.index}]`) - content.indexOf(`[${b.index}]`),
  );

  for (const citation of sorted) {
    const marker = `[${citation.index}]`;
    const idx = remaining.indexOf(marker);
    if (idx === -1) continue;
    const before = remaining.slice(0, idx);
    if (before) {
      parts.push(
        <span key={key++} className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{before}</ReactMarkdown>
        </span>,
      );
    }
    parts.push(<CitationBadge key={key++} citation={citation} />);
    remaining = remaining.slice(idx + marker.length);
  }
  if (remaining) {
    parts.push(
      <span key={key++} className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{remaining}</ReactMarkdown>
      </span>,
    );
  }
  if (isStreaming) {
    parts.push(<span key={key++} className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 rounded-sm" />);
  }

  return <>{parts}</>;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={clsx(
        "flex gap-3 px-4 py-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          "shrink-0 flex items-center justify-center w-8 h-8 rounded-xl mt-0.5",
          isUser ? "bg-indigo-600" : "bg-slate-700",
        )}
      >
        {isUser ? <User size={15} className="text-white" /> : <Bot size={15} className="text-indigo-400" />}
      </div>

      {/* Bubble */}
      <div
        className={clsx(
          "max-w-[80%] flex flex-col gap-1.5",
          isUser ? "items-end" : "items-start",
        )}
      >
        {/* Rewritten query badge */}
        {message.rewrittenQuery && message.rewrittenQuery !== message.content && (
          <div className="flex items-center gap-1 text-[10px] text-slate-500 bg-slate-800/60 border border-slate-700 rounded-full px-2 py-0.5">
            <Sparkles size={9} className="text-indigo-400" />
            <span>Searched: <em className="text-slate-400 not-italic">{message.rewrittenQuery}</em></span>
          </div>
        )}

        {/* Content */}
        <div
          className={clsx(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-indigo-600 text-white rounded-tr-md"
              : "bg-slate-800/80 border border-slate-700/60 text-slate-100 rounded-tl-md",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            renderContentWithCitations(message)
          )}
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-slate-600 px-1">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}
