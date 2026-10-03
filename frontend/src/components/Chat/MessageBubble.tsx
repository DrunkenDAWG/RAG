// src/components/Chat/MessageBubble.tsx
// Renders a single chat message with Markdown, citation badges, and streaming cursor.
import type React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { Bot, User, Sparkles } from "lucide-react";
import { CitationBadge } from "./CitationPopover";
import type { Message, Source } from "../../types";

interface Props {
  message: Message;
  onCitationClick?: (source: Source) => void;
}

// Find marker for citation index (supports [1], [Doc 1], [doc 1], [Doc1])
function findMarker(text: string, index: number): { marker: string; idx: number } | null {
  const variations = [
    `[Doc ${index}]`,
    `[doc ${index}]`,
    `[Doc${index}]`,
    `[doc${index}]`,
    `[${index}]`,
  ];
  for (const m of variations) {
    const idx = text.indexOf(m);
    if (idx !== -1) {
      return { marker: m, idx };
    }
  }
  return null;
}

// Inject citation pill buttons after references
function renderContentWithCitations(
  message: Message,
  onCitationClick?: (source: Source) => void,
) {
  const { content, citations, isStreaming } = message;
  if (citations.length === 0) {
    return (
      <div className="prose prose-invert prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 rounded-sm" />
        )}
      </div>
    );
  }

  const parts: (string | React.ReactNode)[] = [];
  let remaining = content;
  let key = 0;

  // Find all citations present in remaining
  while (remaining.length > 0) {
    let earliestMatch: { citation: any; marker: string; idx: number } | null = null;

    for (const citation of citations) {
      const match = findMarker(remaining, citation.index);
      if (match && (earliestMatch === null || match.idx < earliestMatch.idx)) {
        earliestMatch = { citation, marker: match.marker, idx: match.idx };
      }
    }

    if (!earliestMatch) {
      parts.push(
        <span key={key++} className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{remaining}</ReactMarkdown>
        </span>,
      );
      break;
    }

    const before = remaining.slice(0, earliestMatch.idx);
    if (before) {
      parts.push(
        <span key={key++} className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{before}</ReactMarkdown>
        </span>,
      );
    }

    parts.push(
      <CitationBadge
        key={key++}
        citation={earliestMatch.citation}
        onCitationClick={onCitationClick}
      />,
    );

    remaining = remaining.slice(earliestMatch.idx + earliestMatch.marker.length);
  }

  if (isStreaming) {
    parts.push(
      <span
        key={key++}
        className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 rounded-sm"
      />,
    );
  }

  return <>{parts}</>;
}

export function MessageBubble({ message, onCitationClick }: Props) {
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
            renderContentWithCitations(message, onCitationClick)
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
