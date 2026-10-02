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
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between px-2 py-1">
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Sessions
        </span>
        <button
          onClick={onCreate}
          disabled={loading}
          title="New session"
          className="rounded-md p-1 text-slate-400 hover:bg-slate-700 hover:text-indigo-400 transition-colors"
        >
          <Plus size={15} />
        </button>
      </div>

      <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto pr-1">
        {sessions.length === 0 && (
          <p className="px-3 py-2 text-xs text-slate-500 italic">
            No sessions yet — click + to start
          </p>
        )}
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={clsx(
              "group flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer transition-colors",
              s.session_id === activeId
                ? "bg-indigo-600/30 border border-indigo-500/40"
                : "hover:bg-slate-700/60 border border-transparent",
            )}
            onClick={() => onSelect(s.session_id)}
          >
            <MessageSquare size={13} className="shrink-0 text-indigo-400" />

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
                className="flex-1 min-w-0 bg-slate-800 text-xs text-white rounded px-1 py-0.5 outline-none border border-indigo-500"
              />
            ) : (
              <span className="flex-1 min-w-0 truncate text-xs text-slate-200">
                {s.label}
              </span>
            )}

            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              {editingId === s.session_id ? (
                <button
                  onClick={(e) => { e.stopPropagation(); commitEdit(s.session_id); }}
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  <Check size={12} />
                </button>
              ) : (
                <button
                  onClick={(e) => { e.stopPropagation(); startEdit(s); }}
                  className="text-slate-400 hover:text-slate-200"
                >
                  <Edit2 size={12} />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(s.session_id); }}
                className="text-slate-400 hover:text-red-400"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
