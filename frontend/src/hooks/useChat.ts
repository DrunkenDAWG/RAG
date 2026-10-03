// src/hooks/useChat.ts
import { useCallback, useRef, useState } from "react";
import { streamChat } from "../lib/api";
import type { Citation, Message, Source } from "../types";

let msgCounter = 0;
const uid = () => `msg_${++msgCounter}_${Date.now()}`;

function parseCitations(text: string, sources: Source[]): Citation[] {
  // Match patterns like [1], [2], [1,2], [Doc 1], [doc 2]
  const refs = new Set<number>();
  const pattern = /\[(?:(?:Doc|doc)\s*)?(\d+(?:,\s*\d+)*)\]/g;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    m[1].split(",").forEach((n) => refs.add(parseInt(n.trim(), 10)));
  }
  return Array.from(refs)
    .filter((i) => sources[i - 1])
    .map((i) => ({ index: i, source: sources[i - 1] }));
}

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (query: string, tutorMode: boolean = false) => {
      if (!sessionId || isStreaming) return;

      // Cancel any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Add user message
      const userMsg: Message = {
        id: uid(),
        role: "user",
        content: query,
        sources: [],
        citations: [],
        timestamp: new Date(),
      };

      // Placeholder assistant message (streaming)
      const assistantMsgId = uid();
      const assistantMsg: Message = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        sources: [],
        citations: [],
        isStreaming: true,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const patch = (updater: (m: Message) => Partial<Message>) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsgId ? { ...m, ...updater(m) } : m)),
        );
      };

      try {
        await streamChat({
          sessionId,
          query,
          tutorMode,
          signal: controller.signal,

          onRewrittenQuery: (q) => patch(() => ({ rewrittenQuery: q })),

          onToken: (delta) =>
            patch((m) => ({ content: m.content + delta })),

          onDone: (sources) =>
            patch((m) => ({
              isStreaming: false,
              sources,
              citations: parseCitations(m.content, sources),
            })),

          onCached: (answer, sources) =>
            patch(() => ({
              content: answer,
              isStreaming: false,
              sources,
              citations: parseCitations(answer, sources),
            })),

          onError: (detail) =>
            patch(() => ({
              content: `⚠️ ${detail}`,
              isStreaming: false,
            })),
        });
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          patch(() => ({
            content: "⚠️ Request was interrupted.",
            isStreaming: false,
          }));
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, isStreaming],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
    );
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isStreaming, sendMessage, stopStreaming, clearMessages };
}
