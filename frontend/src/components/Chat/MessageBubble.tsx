// src/components/Chat/MessageBubble.tsx
// Renders a single chat message with Markdown, citation badges, and streaming cursor.
import type React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { Bot, User, Search } from "lucide-react";
import { CitationBadge, PreviewPageButton } from "./CitationPopover";
import { formatPages } from "../../lib/utils";
import type { Message, Source } from "../../types";

interface Props {
  message: Message;
  onCitationClick?: (source: Source) => void;
  onPreviewPage?: (source: Source) => void;
}

const sourceKey = (s: Source) => `${s.doc_id}::${s.page ?? ""}-${s.page_end ?? ""}`;

// Sources actually cited in the answer, one entry per (document, page span)
function citedSources(message: Message): Source[] {
  const seen = new Set<string>();
  const out: Source[] = [];
  for (const { source } of message.citations) {
    const key = sourceKey(source);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(source);
  }
  return out;
}

function SourcesList({
  sources,
  onPreviewPage,
}: {
  sources: Source[];
  onPreviewPage?: (source: Source) => void;
}) {
  return (
    <div className="mt-3 pt-2.5 border-t border-border-subtle flex flex-col gap-1.5">
      <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">Sources</span>
      {sources.map((source) => (
        <div
          key={sourceKey(source)}
          className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-secondary"
        >
          <span>
            📄 {source.filename}
            {source.page ? ` — ${formatPages(source)}` : ""}
          </span>
          {source.page && onPreviewPage && (
            <PreviewPageButton onClick={() => onPreviewPage(source)} />
          )}
        </div>
      ))}
    </div>
  );
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
  onPreviewPage?: (source: Source) => void,
) {
  const { content, citations, isStreaming } = message;
  if (citations.length === 0) {
    return (
      <div className="prose prose-invert text-xs sm:text-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        {isStreaming && (
          <span className="inline-block w-1 h-3.5 bg-white animate-pulse ml-1 align-middle" />
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
        <span key={key++} className="prose prose-invert text-xs sm:text-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{remaining}</ReactMarkdown>
        </span>,
      );
      break;
    }

    const before = remaining.slice(0, earliestMatch.idx);
    if (before) {
      parts.push(
        <span key={key++} className="prose prose-invert text-xs sm:text-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{before}</ReactMarkdown>
        </span>,
      );
    }

    parts.push(
      <CitationBadge
        key={key++}
        citation={earliestMatch.citation}
        onCitationClick={onCitationClick}
        onPreviewPage={onPreviewPage}
      />,
    );

    remaining = remaining.slice(earliestMatch.idx + earliestMatch.marker.length);
  }

  if (isStreaming) {
    parts.push(
      <span
        key={key++}
        className="inline-block w-1 h-3.5 bg-white animate-pulse ml-1 align-middle"
      />,
    );
  }

  return <>{parts}</>;
}

export function MessageBubble({ message, onCitationClick, onPreviewPage }: Props) {
  const isUser = message.role === "user";
  const sources = isUser || message.isStreaming ? [] : citedSources(message);

  return (
    <div
      className={clsx(
        "flex gap-3 px-6 py-2",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          "shrink-0 flex items-center justify-center w-7 h-7 rounded-md mt-0.5 border text-xs",
          isUser
            ? "bg-white text-black border-white"
            : "bg-subtle text-text-secondary border-border-subtle",
        )}
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </div>

      {/* Bubble */}
      <div
        className={clsx(
          "max-w-[82%] flex flex-col gap-1.5",
          isUser ? "items-end" : "items-start",
        )}
      >
        {/* Rewritten query badge */}
        {message.rewrittenQuery && message.rewrittenQuery !== message.content && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted bg-subtle border border-border-subtle rounded-md px-2 py-0.5">
            <Search size={9} />
            <span>Refined: <span className="text-text-secondary">{message.rewrittenQuery}</span></span>
          </div>
        )}

        {/* Content */}
        <div
          className={clsx(
            "rounded-xl px-4 py-3 text-xs sm:text-sm leading-relaxed border",
            isUser
              ? "bg-subtle border-border-strong text-text-primary"
              : "bg-surface/80 border-border-subtle text-text-primary",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            renderContentWithCitations(message, onCitationClick, onPreviewPage)
          )}
          {sources.length > 0 && (
            <SourcesList sources={sources} onPreviewPage={onPreviewPage} />
          )}
        </div>

        {/* Timestamp */}
        <span className="text-[10px] font-mono text-text-muted px-1">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}
