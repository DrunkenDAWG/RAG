// src/lib/api.ts
// ───────────────
// Typed API client for all backend interactions.

import type { Document, FlashcardDeck, Quiz, Session, Source, SSEEvent } from "../types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// ── Sessions ──────────────────────────────────────────────────────────────────

export async function createSession(): Promise<Session> {
  const res = await fetch(`${BASE}/api/v1/sessions`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`);
  const data = await res.json();
  return {
    session_id: data.session_id,
    created_at: new Date().toISOString(),
    label: `Session ${new Date().toLocaleTimeString()}`,
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/api/v1/sessions/${sessionId}`, { method: "DELETE" });
}

// ── Documents ──────────────────────────────────────────────────────────────────

export async function uploadDocuments(
  sessionId: string,
  files: File[],
  onProgress?: (pct: number) => void,
): Promise<Document[]> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/api/v1/documents/upload`);
    xhr.setRequestHeader("X-Session-Id", sessionId);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve(
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            data.map((d: any) => ({
              document_id: d.document_id ?? d.doc_id,
              filename: d.filename,
              chunk_count: d.chunk_count,
            })),
          );
        } catch {
          reject(new Error("Invalid response from upload endpoint"));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
      }
    });
    xhr.addEventListener("error", () => reject(new Error("Network error during upload")));
    xhr.send(form);
  });
}

export async function listDocuments(sessionId: string): Promise<Document[]> {
  const res = await fetch(`${BASE}/api/v1/documents`, {
    headers: { "X-Session-Id": sessionId },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function deleteDocument(
  sessionId: string,
  documentId: string,
): Promise<void> {
  await fetch(`${BASE}/api/v1/documents/${documentId}`, {
    method: "DELETE",
    headers: { "X-Session-Id": sessionId },
  });
}

// ── Chat streaming ────────────────────────────────────────────────────────────

export interface ChatStreamOptions {
  sessionId: string;
  query: string;
  model?: string;
  topK?: number;
  topN?: number;
  useCache?: boolean;
  tutorMode?: boolean;
  onToken: (delta: string) => void;
  onRewrittenQuery: (q: string) => void;
  onDone: (sources: Source[]) => void;
  onError: (detail: string) => void;
  onCached: (answer: string, sources: Source[]) => void;
  signal?: AbortSignal;
}

export async function streamChat(opts: ChatStreamOptions): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: opts.sessionId,
      query: opts.query,
      model: opts.model ?? null,
      top_k: opts.topK ?? 20,
      top_n: opts.topN ?? 5,
      use_cache: opts.useCache ?? true,
      tutor_mode: opts.tutorMode ?? false,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    opts.onError(`Backend returned ${res.status}: ${res.statusText}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice("data:".length).trim();
      if (!jsonStr || jsonStr === "[DONE]") continue;

      try {
        const event = JSON.parse(jsonStr) as SSEEvent;
        switch (event.type) {
          case "token":           opts.onToken(event.content); break;
          case "rewritten_query": opts.onRewrittenQuery(event.content); break;
          case "done":            opts.onDone(event.sources); break;
          case "error":           opts.onError(event.detail); break;
          case "cached":          opts.onCached(event.answer, event.sources); break;
        }
      } catch {
        // malformed SSE line — skip
      }
    }
  }
}

// ── Study / Active Recall ────────────────────────────────────────────────────

export async function generateQuiz(
  sessionId: string,
  topic: string,
): Promise<Quiz> {
  const res = await fetch(`${BASE}/api/v1/study/generate-quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      topic,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to generate quiz: ${res.statusText}`,
    );
  }

  return res.json();
}

export async function generateFlashcards(
  sessionId: string,
  topic: string,
): Promise<FlashcardDeck> {
  const res = await fetch(`${BASE}/api/v1/study/generate-flashcards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      topic,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to generate flashcards: ${res.statusText}`,
    );
  }

  return res.json();
}

