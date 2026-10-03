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
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-900/60 hover:bg-indigo-600 border border-indigo-400/50 hover:border-indigo-300 text-indigo-300 hover:text-white text-[11px] font-semibold tracking-wide transition-all shadow-sm hover:scale-105 active:scale-95 cursor-pointer"
        title={`Click to highlight in Knowledge Base: ${citation.source.filename}`}
      >
        <BookOpen size={10} className="text-indigo-400 group-hover:text-white" />
        <span>Doc {citation.index}</span>
      </button>

      {open && (
        <div className="absolute z-50 bottom-7 left-0 w-72 rounded-xl border border-slate-600 bg-slate-800 shadow-2xl p-3 text-xs">
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-1.5 text-indigo-400 font-semibold">
              <BookOpen size={12} />
              <span className="truncate max-w-[200px]">{citation.source.filename}</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-500 hover:text-slate-300 shrink-0"
            >
              <X size={12} />
            </button>
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-3 text-slate-400 border-b border-slate-700 pb-2 mb-2">
            <span>Chunk <strong className="text-slate-300">{citation.source.chunk_index}</strong></span>
            <span>Score <strong className="text-slate-300">{citation.source.score.toFixed(3)}</strong></span>
          </div>

          {/* Doc ID */}
          <p className="text-slate-500 truncate font-mono text-[10px]">
            {citation.source.doc_id}
          </p>
        </div>
      )}
    </span>
  );
}
