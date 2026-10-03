// src/types/index.ts
// ──────────────────
// Shared TypeScript types used across hooks and components.

export interface Session {
  session_id: string;
  created_at: string;
  label: string; // user-editable display name
}

export interface Document {
  document_id: string;
  filename: string;
  chunk_count: number;
}

export interface Source {
  doc_id: string;
  filename: string;
  chunk_index: number;
  score: number;
}

export type MessageRole = "user" | "assistant" | "system";

export interface Citation {
  index: number;   // [1], [2] … as they appear in the text
  source: Source;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;          // full accumulated text
  sources: Source[];
  citations: Citation[];    // parsed from content
  isStreaming?: boolean;
  rewrittenQuery?: string;
  timestamp: Date;
}

// SSE event payloads emitted by the backend
export type SSEEvent =
  | { type: "rewritten_query"; content: string }
  | { type: "token";           content: string }
  | { type: "done";            sources: Source[] }
  | { type: "error";           detail: string }
  | { type: "cached";          answer: string; sources: Source[] };

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
}

export interface Quiz {
  questions: QuizQuestion[];
}

export interface Flashcard {
  front: string;
  back: string;
  key_term: string;
}

export interface FlashcardDeck {
  cards: Flashcard[];
}

