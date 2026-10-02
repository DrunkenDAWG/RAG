// src/components/Sidebar/DocumentList.tsx
import { FileText, Trash2, Layers } from "lucide-react";
import type { Document } from "../../types";

interface Props {
  documents: Document[];
  loading: boolean;
  onDelete: (id: string) => void;
}

export function DocumentList({ documents, loading, onDelete }: Props) {
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

      <div className="flex flex-col gap-0.5 max-h-80 overflow-y-auto pr-1">
        {documents.map((doc) => (
          <div
            key={doc.document_id}
            className="group flex items-start gap-2 rounded-lg px-3 py-2 hover:bg-slate-700/50 transition-colors"
          >
            <FileText size={13} className="shrink-0 mt-0.5 text-slate-400" />
            <div className="flex-1 min-w-0">
              <p className="truncate text-xs text-slate-200 leading-tight">
                {doc.filename}
              </p>
              <p className="text-xs text-slate-500">{doc.chunk_count} chunks</p>
            </div>
            <button
              onClick={() => onDelete(doc.document_id)}
              title="Remove document"
              className="shrink-0 mt-0.5 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
