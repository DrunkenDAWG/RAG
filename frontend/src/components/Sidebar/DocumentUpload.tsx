// src/components/Sidebar/DocumentUpload.tsx
import { Upload, Loader2 } from "lucide-react";
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
          "flex items-center justify-center gap-2 rounded-lg border border-dashed px-3 py-2.5 text-xs font-medium transition-all",
          disabled || isUploading
            ? "border-border-subtle text-text-muted cursor-not-allowed opacity-50"
            : "border-border-subtle text-text-secondary hover:text-white hover:border-border-strong hover:bg-subtle/60 cursor-pointer",
        )}
      >
        {isUploading ? (
          <Loader2 size={14} className="animate-spin text-text-primary" />
        ) : (
          <Upload size={14} />
        )}
        <span>{isUploading ? "Uploading…" : "Upload Files (.pdf, .docx, .txt)"}</span>
      </button>

      {/* Per-file progress rows */}
      {uploads.length > 0 && (
        <div className="flex flex-col gap-1.5 pt-1">
          {uploads.map((u, i) => (
            <div key={i} className="flex flex-col gap-1 p-2 rounded bg-subtle border border-border-subtle">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="truncate max-w-[70%] text-text-secondary">{u.filename}</span>
                <span className="text-text-muted">
                  {u.status === "done" ? "Done" : u.status === "error" ? "Failed" : `${u.progress}%`}
                </span>
              </div>
              <div className="h-1 w-full rounded-full bg-canvas border border-border-subtle overflow-hidden">
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-300",
                    u.status === "error" ? "bg-red-500" : "bg-white",
                  )}
                  style={{ width: `${u.progress}%` }}
                />
              </div>
              {u.error && (
                <p className="text-[10px] text-red-400 truncate">{u.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
