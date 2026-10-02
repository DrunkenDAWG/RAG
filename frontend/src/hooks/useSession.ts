// src/hooks/useSession.ts
import { useCallback, useEffect, useState } from "react";
import { createSession, deleteSession } from "../lib/api";
import type { Session } from "../types";

const STORAGE_KEY = "rag_sessions";

function loadSessions(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

export function useSession() {
  const [sessions, setSessions] = useState<Session[]>(loadSessions);
  const [activeId, setActiveId] = useState<string | null>(
    () => sessions[0]?.session_id ?? null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  const newSession = useCallback(async () => {
    setLoading(true);
    try {
      const s = await createSession();
      setSessions((prev) => [s, ...prev]);
      setActiveId(s.session_id);
      return s;
    } finally {
      setLoading(false);
    }
  }, []);

  const removeSession = useCallback(
    async (id: string) => {
      await deleteSession(id).catch(() => {});
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (activeId === id) setActiveId(sessions.find((s) => s.session_id !== id)?.session_id ?? null);
    },
    [activeId, sessions],
  );

  const renameSession = useCallback((id: string, label: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.session_id === id ? { ...s, label } : s)),
    );
  }, []);

  const activeSession = sessions.find((s) => s.session_id === activeId) ?? null;

  return { sessions, activeSession, activeId, loading, newSession, removeSession, renameSession, setActiveId };
}
