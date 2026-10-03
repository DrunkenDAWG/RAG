// src/components/Sidebar/DocumentList.tsx
import { FileText, Trash2, Layers } from "lucide-react";
import clsx from "clsx";
import type { Document } from "../../types";

interface Props {
  documents: Document[];
  loading: boolean;
  onDelete: (id: string) => void;
  highlightedDocId?: string | null;
}

export function DocumentList({ documents, loading, onDelete, highlightedDocId }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 px-2 py-1">
        <Layers size={12} className="text-slate-400" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Documents
        </span>
        {documents.length > 0 && (
          <span className="ml-auto text-xs font-medium text-slate-500 bg-slate-700 rounded-full px-1.5">
            {documents.length}
          </span>
        )}
      </div>

      {loading && (
        <p className="px-3 py-2 text-xs text-slate-500 animate-pulse">Loading…</p>
      )}

      {!loading && documents.length === 0 && (
        <p className="px-3 py-2 text-xs text-slate-500 italic">
          No documents uploaded yet
        </p>
      )}

      <div className="flex flex-col gap-1 max-h-80 overflow-y-auto pr-1">
        {documents.map((doc) => {
          const isHighlighted =
            highlightedDocId &&
            (doc.document_id === highlightedDocId ||
              doc.filename.toLowerCase() === highlightedDocId.toLowerCase());

          return (
            <div
              key={doc.document_id}
              className={clsx(
                "group flex items-start gap-2 rounded-lg px-3 py-2 transition-all duration-300",
                isHighlighted
                  ? "bg-indigo-950/80 border border-indigo-400 ring-2 ring-indigo-400/50 shadow-md shadow-indigo-500/30 scale-[1.02]"
                  : "hover:bg-slate-700/50 border border-transparent",
              )}
            >
              <FileText
                size={13}
                className={clsx(
                  "shrink-0 mt-0.5 transition-colors",
                  isHighlighted ? "text-indigo-400 animate-bounce" : "text-slate-400",
                )}
              />
              <div className="flex-1 min-w-0">
                <p
                  className={clsx(
                    "truncate text-xs leading-tight transition-colors",
                    isHighlighted ? "text-indigo-200 font-semibold" : "text-slate-200",
                  )}
                >
                  {doc.filename}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <p className="text-xs text-slate-500">{doc.chunk_count} chunks</p>
                  {isHighlighted && (
                    <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                      • Cited
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => onDelete(doc.document_id)}
                title="Remove document"
                className="shrink-0 mt-0.5 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
              >
                <Trash2 size={12} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
