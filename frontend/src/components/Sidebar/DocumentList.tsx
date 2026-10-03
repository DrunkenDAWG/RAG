// src/components/Sidebar/DocumentList.tsx
import { FileText, Trash2, Files } from "lucide-react";
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
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-text-muted">
          <Files size={12} />
          <span>Knowledge Base</span>
        </div>
        {documents.length > 0 && (
          <span className="text-[10px] font-mono text-text-muted bg-subtle border border-border-subtle rounded px-1.5">
            {documents.length}
          </span>
        )}
      </div>

      {loading && (
        <p className="px-2 py-2 text-xs font-mono text-text-muted animate-pulse">Loading documents…</p>
      )}

      {!loading && documents.length === 0 && (
        <p className="px-2 py-2 text-xs text-text-muted italic">
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
                "group flex items-start gap-2.5 rounded-lg px-2.5 py-2 transition-all border text-xs",
                isHighlighted
                  ? "bg-subtle border-border-strong text-white shadow-subtle ring-1 ring-white/20"
                  : "border-transparent text-text-secondary hover:bg-subtle/50 hover:text-text-primary hover:border-border-subtle",
              )}
            >
              <FileText
                size={13}
                className={clsx(
                  "shrink-0 mt-0.5 transition-colors",
                  isHighlighted ? "text-white" : "text-text-muted group-hover:text-text-secondary",
                )}
              />
              <div className="flex-1 min-w-0">
                <p className="truncate text-xs leading-tight font-medium">
                  {doc.filename}
                </p>
                <div className="flex items-center gap-2 mt-0.5 font-mono text-[10px] text-text-muted">
                  <span>{doc.chunk_count} chunks</span>
                  {isHighlighted && (
                    <span className="text-white font-medium">
                      [Cited]
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => onDelete(doc.document_id)}
                title="Delete document"
                className="shrink-0 mt-0.5 text-text-muted hover:text-white opacity-0 group-hover:opacity-100 transition-opacity p-0.5 cursor-pointer"
              >
                <Trash2 size={11} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
