// src/hooks/useDocuments.ts
import { useCallback, useEffect, useState } from "react";
import { deleteDocument, listDocuments, uploadDocuments } from "../lib/api";
import type { Document } from "../types";

export interface UploadState {
  filename: string;
  progress: number;  // 0-100
  status: "uploading" | "done" | "error";
  error?: string;
  warning?: string;
}

export function useDocuments(sessionId: string | null) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!sessionId) { setDocuments([]); return; }
    setLoading(true);
    try {
      const docs = await listDocuments(sessionId);
      setDocuments(docs);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setDocuments([]);
    refresh();
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = useCallback(
    async (files: File[]) => {
      if (!sessionId || files.length === 0) return;

      // Initialise upload state entries
      const initial: UploadState[] = files.map((f) => ({
        filename: f.name,
        progress: 0,
        status: "uploading",
      }));
      setUploads(initial);

      let needsAttention = false;
      try {
        const results = await uploadDocuments(sessionId, files, (pct) => {
          setUploads((prev) =>
            prev.map((u) => ({ ...u, progress: pct })),
          );
        });
        const warnings = new Map(
          results.filter((r) => r.warning).map((r) => [r.filename, r.warning as string]),
        );
        needsAttention = warnings.size > 0;
        setUploads((prev) =>
          prev.map((u) => ({
            ...u,
            progress: 100,
            status: "done",
            warning: warnings.get(u.filename),
          })),
        );
        await refresh();
      } catch (err) {
        needsAttention = true;
        setUploads((prev) =>
          prev.map((u) => ({
            ...u,
            status: "error",
            error: err instanceof Error ? err.message : "Upload failed",
          })),
        );
      } finally {
        // Clear upload indicators (longer when there's something to read)
        setTimeout(() => setUploads([]), needsAttention ? 10000 : 3000);
      }
    },
    [sessionId, refresh],
  );

  const remove = useCallback(
    async (documentId: string) => {
      if (!sessionId) return;
      await deleteDocument(sessionId, documentId);
      setDocuments((prev) => prev.filter((d) => d.document_id !== documentId));
    },
    [sessionId],
  );

  return { documents, uploads, loading, upload, remove, refresh };
}
