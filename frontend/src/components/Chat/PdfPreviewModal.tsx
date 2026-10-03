// src/components/Chat/PdfPreviewModal.tsx
// Opens an uploaded PDF on the cited page using the browser's built-in PDF viewer.
import { useEffect, useState } from "react";
import { FileText, Loader2, X } from "lucide-react";
import { fetchDocumentFile } from "../../lib/api";
import { formatPages } from "../../lib/utils";
import type { Source } from "../../types";

interface Props {
  sessionId: string;
  source: Source;
  onClose: () => void;
}

export function PdfPreviewModal({ sessionId, source, onClose }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let url: string | null = null;

    fetchDocumentFile(sessionId, source.doc_id, controller.signal)
      .then((blob) => {
        url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
        setBlobUrl(url);
      })
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err.message);
      });

    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, source.doc_id]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const pageHash = source.page ? `#page=${source.page}` : "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/80 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl h-[90vh] bg-surface border border-border-strong rounded-xl shadow-modal flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border-subtle bg-surface">
          <div className="flex items-center gap-2 min-w-0 text-xs">
            <FileText size={14} className="text-text-secondary shrink-0" />
            <span className="font-semibold text-text-primary truncate">{source.filename}</span>
            {source.page && (
              <span className="font-mono text-text-muted shrink-0">— {formatPages(source)}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary rounded-md hover:bg-subtle transition-colors cursor-pointer"
            title="Close preview (Esc)"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 bg-canvas">
          {error ? (
            <div className="flex h-full items-center justify-center text-xs text-text-muted">
              {error}
            </div>
          ) : blobUrl ? (
            <iframe
              // key forces a fresh viewer so the #page fragment is always honoured
              key={`${blobUrl}${pageHash}`}
              src={`${blobUrl}${pageHash}`}
              title={`${source.filename} preview`}
              className="w-full h-full border-0"
            />
          ) : (
            <div className="flex h-full items-center justify-center gap-2 text-xs text-text-muted">
              <Loader2 size={14} className="animate-spin" /> Loading document…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
