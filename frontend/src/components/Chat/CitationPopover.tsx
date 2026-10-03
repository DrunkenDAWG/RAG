// src/components/Chat/CitationPopover.tsx
// Renders a numbered badge that opens a popover with source metadata.
import { useState, useRef, useEffect } from "react";
import { BookOpen, X } from "lucide-react";
import type { Citation, Source } from "../../types";

interface BadgeProps {
  citation: Citation;
  onCitationClick?: (source: Source) => void;
}

export function CitationBadge({ citation, onCitationClick }: BadgeProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen((o) => !o);
    onCitationClick?.(citation.source);
  };

  return (
    <span ref={ref} className="relative inline-block align-middle mx-1 my-0.5">
      <button
        onClick={handleClick}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-subtle hover:bg-canvas border border-border-subtle hover:border-border-strong text-text-primary text-[10px] font-mono transition-all cursor-pointer shadow-subtle active:scale-95"
        title={`Highlight in Documents: ${citation.source.filename}`}
      >
        <BookOpen size={10} className="text-text-muted" />
        <span>Doc {citation.index}</span>
      </button>

      {open && (
        <div className="absolute z-50 bottom-7 left-0 w-72 rounded-lg border border-border-strong bg-surface shadow-dropdown p-3 text-xs">
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-1.5 text-text-primary font-medium">
              <BookOpen size={12} className="text-text-secondary" />
              <span className="truncate max-w-[200px]">{citation.source.filename}</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-text-muted hover:text-text-primary shrink-0 transition-colors"
            >
              <X size={12} />
            </button>
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-3 text-text-muted font-mono text-[11px] border-b border-border-subtle pb-2 mb-2">
            <span>Chunk: <strong className="text-text-secondary font-normal">{citation.source.chunk_index}</strong></span>
            <span>Score: <strong className="text-text-secondary font-normal">{citation.source.score.toFixed(3)}</strong></span>
          </div>

          {/* Doc ID */}
          <p className="text-text-muted truncate font-mono text-[10px]">
            ID: {citation.source.doc_id}
          </p>
        </div>
      )}
    </span>
  );
}
