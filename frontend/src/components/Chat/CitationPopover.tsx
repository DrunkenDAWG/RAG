// src/components/Chat/CitationPopover.tsx
// Renders a numbered badge that opens a popover with source metadata.
import { useState, useRef, useEffect } from "react";
import { BookOpen, X } from "lucide-react";
import type { Citation } from "../../types";

interface BadgeProps {
  citation: Citation;
}

export function CitationBadge({ citation }: BadgeProps) {
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

  return (
    <span ref={ref} className="relative inline-block align-middle mx-0.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold leading-none transition-colors"
        title={`Source: ${citation.source.filename}`}
      >
        {citation.index}
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
