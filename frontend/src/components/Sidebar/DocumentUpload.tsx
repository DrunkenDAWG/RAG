// src/components/Sidebar/DocumentUpload.tsx
import { FileUp, Loader2 } from "lucide-react";
import { useRef } from "react";
import clsx from "clsx";
import type { UploadState } from "../../hooks/useDocuments";

interface Props {
  uploads: UploadState[];
  disabled: boolean;
  onUpload: (files: File[]) => void;
}

export function DocumentUpload({ uploads, disabled, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    onUpload(Array.from(files));
  };

  const isUploading = uploads.some((u) => u.status === "uploading");

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {/* Drop zone / button */}
      <button
        disabled={disabled || isUploading}
        onClick={() => inputRef.current?.click()}
        onDrop={(e) => {
          e.preventDefault();
          handleFiles(e.dataTransfer.files);
        }}
        onDragOver={(e) => e.preventDefault()}
        className={clsx(
          "flex items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-3 text-sm font-medium transition-all",
          disabled || isUploading
            ? "border-slate-700 text-slate-600 cursor-not-allowed"
            : "border-indigo-500/50 text-indigo-400 hover:border-indigo-400 hover:bg-indigo-500/10 cursor-pointer",
        )}
      >
        {isUploading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <FileUp size={16} />
        )}
        {isUploading ? "Uploading…" : "Upload Documents"}
      </button>

      {/* Per-file progress rows */}
      {uploads.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {uploads.map((u, i) => (
            <div key={i} className="flex flex-col gap-0.5">
              <div className="flex items-center justify-between text-xs">
                <span className="truncate max-w-[70%] text-slate-300">{u.filename}</span>
                <span
                  className={clsx(
                    "font-medium",
                    u.status === "done"  && "text-emerald-400",
                    u.status === "error" && "text-red-400",
                    u.status === "uploading" && "text-indigo-400",
                  )}
                >
                  {u.status === "done"  ? "Done"
                   : u.status === "error" ? "Error"
                   : `${u.progress}%`}
                </span>
              </div>
              <div className="h-1 w-full rounded-full bg-slate-700 overflow-hidden">
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-300",
                    u.status === "error" ? "bg-red-500" : "bg-indigo-500",
                  )}
                  style={{ width: `${u.progress}%` }}
                />
              </div>
              {u.error && (
                <p className="text-xs text-red-400 truncate">{u.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
