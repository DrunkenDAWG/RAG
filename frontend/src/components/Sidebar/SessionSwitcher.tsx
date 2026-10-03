// src/components/Sidebar/SessionSwitcher.tsx
import { MessageSquare, Plus, Trash2, Edit2, Check } from "lucide-react";
import { useState } from "react";
import clsx from "clsx";
import type { Session } from "../../types";

interface Props {
  sessions: Session[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, label: string) => void;
}

export function SessionSwitcher({ sessions, activeId, loading, onSelect, onCreate, onDelete, onRename }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEdit = (s: Session) => {
    setEditingId(s.session_id);
    setDraft(s.label);
  };

  const commitEdit = (id: string) => {
    if (draft.trim()) onRename(id, draft.trim());
    setEditingId(null);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-mono uppercase tracking-wider text-text-muted">
          Sessions
        </span>
        <button
          onClick={onCreate}
          disabled={loading}
          title="New session"
          className="rounded-md p-1 text-text-muted hover:text-text-primary hover:bg-subtle border border-transparent hover:border-border-subtle transition-all cursor-pointer"
        >
          <Plus size={13} />
        </button>
      </div>

      <div className="flex flex-col gap-1 max-h-60 overflow-y-auto pr-1">
        {sessions.length === 0 && (
          <p className="px-2 py-2 text-xs text-text-muted italic">
            No sessions yet — click + to start
          </p>
        )}
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={clsx(
              "group flex items-center gap-2 rounded-lg px-2.5 py-1.5 cursor-pointer transition-all border text-xs",
              s.session_id === activeId
                ? "bg-subtle border-border-strong text-white shadow-subtle"
                : "border-transparent text-text-secondary hover:bg-subtle/50 hover:text-text-primary hover:border-border-subtle",
            )}
            onClick={() => onSelect(s.session_id)}
          >
            <MessageSquare size={13} className="shrink-0 text-text-muted" />

            {editingId === s.session_id ? (
              <input
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit(s.session_id);
                  if (e.key === "Escape") setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
                className="flex-1 min-w-0 bg-canvas text-xs text-white rounded px-1.5 py-0.5 outline-none border border-border-strong"
              />
            ) : (
              <span className="flex-1 min-w-0 truncate">
                {s.label}
              </span>
            )}

            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              {editingId === s.session_id ? (
                <button
                  onClick={(e) => { e.stopPropagation(); commitEdit(s.session_id); }}
                  className="text-text-primary hover:text-white p-0.5"
                >
                  <Check size={12} />
                </button>
              ) : (
                <button
                  onClick={(e) => { e.stopPropagation(); startEdit(s); }}
                  className="text-text-muted hover:text-text-primary p-0.5"
                >
                  <Edit2 size={11} />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(s.session_id); }}
                className="text-text-muted hover:text-white p-0.5"
              >
                <Trash2 size={11} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
