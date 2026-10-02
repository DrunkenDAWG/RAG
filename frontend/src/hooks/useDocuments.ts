// src/hooks/useDocuments.ts
import { useCallback, useEffect, useState } from "react";
import { deleteDocument, listDocuments, uploadDocuments } from "../lib/api";
import type { Document } from "../types";

export interface UploadState {
  filename: string;
  progress: number;  // 0-100
  status: "uploading" | "done" | "error";
  error?: string;
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

      try {
        await uploadDocuments(sessionId, files, (pct) => {
          setUploads((prev) =>
            prev.map((u) => ({ ...u, progress: pct })),
          );
        });
        setUploads((prev) =>
          prev.map((u) => ({ ...u, progress: 100, status: "done" })),
        );
        await refresh();
      } catch (err) {
        setUploads((prev) =>
          prev.map((u) => ({
            ...u,
            status: "error",
            error: err instanceof Error ? err.message : "Upload failed",
          })),
        );
      } finally {
        // Clear upload indicators after 3 s
        setTimeout(() => setUploads([]), 3000);
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
