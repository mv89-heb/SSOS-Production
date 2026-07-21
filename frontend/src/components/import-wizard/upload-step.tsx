"use client";
import { useRef, useState } from "react";
import { UploadCloud, FileSpreadsheet, X, ChevronDown, Calendar, HardDrive, FileType } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUploadImport } from "@/hooks/use-imports";
import { cn } from "@/lib/utils";

const ALLOWED_EXTENSIONS = [".xlsx", ".xls", ".csv"];
const MAX_SIZE_MB = 10;

const EXTENSION_LABELS: Record<string, string> = {
  ".xlsx": "Excel",
  ".xls": "Excel (ישן)",
  ".csv": "CSV",
};

interface UploadStepProps {
  onUploaded: (sessionId: number) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadStep({ onUploaded }: UploadStepProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const upload = useUploadImport();

  const validateAndSetFile = (candidate: File) => {
    setLocalError(null);
    const ext = "." + (candidate.name.split(".").pop() ?? "").toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setLocalError(`סוג קובץ לא נתמך (${ext}). ניתן להעלות קבצי Excel או CSV בלבד.`);
      return;
    }
    if (candidate.size > MAX_SIZE_MB * 1024 * 1024) {
      setLocalError(`הקובץ גדול מדי (מקסימום ${MAX_SIZE_MB}MB).`);
      return;
    }
    if (candidate.size === 0) {
      setLocalError("הקובץ ריק.");
      return;
    }
    setFile(candidate);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) validateAndSetFile(dropped);
  };

  const handleUpload = () => {
    if (!file) return;
    upload.mutate(
      { file, sheetName: sheetName.trim() || undefined },
      {
        onSuccess: (session) => {
          if (session.status === "FAILED") {
            setLocalError(session.error_message || "טעינת הקובץ נכשלה. ודא שזהו קובץ מחירון תקין.");
            return;
          }
          onUploaded(session.id);
        },
        onError: (err) => {
          const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
          setLocalError(message || "העלאת הקובץ נכשלה. נסה שוב.");
        },
      }
    );
  };

  const ext = file ? "." + (file.name.split(".").pop() ?? "").toLowerCase() : "";

  return (
    <div className="space-y-5">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-slate-900">העלה מחירון ספק</h2>
        <p className="mt-1 text-sm text-slate-500">גרור קובץ Excel, ואנחנו נזהה בשבילך את כל השאר.</p>
      </div>

      {!file ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-14 text-center transition-colors",
            dragOver ? "border-primary bg-primary/5" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
          )}
        >
          <div className="rounded-full bg-primary/10 p-4">
            <UploadCloud className="text-primary" size={32} />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">גרור קובץ לכאן, או לחץ לבחירה</p>
            <p className="mt-1 text-xs text-slate-400">Excel (xlsx, xls) או CSV · עד {MAX_SIZE_MB}MB</p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => {
              const selected = e.target.files?.[0];
              if (selected) validateAndSetFile(selected);
            }}
          />
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2.5 shadow-sm">
                <FileSpreadsheet className="text-primary" size={24} />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-900">{file.name}</p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <HardDrive size={12} />
                    {formatFileSize(file.size)}
                  </span>
                  <span className="flex items-center gap-1">
                    <FileType size={12} />
                    {EXTENSION_LABELS[ext] ?? ext}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar size={12} />
                    {new Date(file.lastModified).toLocaleDateString("he-IL")}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                setFile(null);
                setLocalError(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="text-slate-400 hover:text-slate-700"
              aria-label="הסרת קובץ"
            >
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      {localError && <p className="text-center text-sm text-red-500">{localError}</p>}

      {file && (
        <div>
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-slate-600"
          >
            <ChevronDown size={14} className={cn("transition-transform", showAdvanced && "rotate-180")} />
            אפשרויות מתקדמות
          </button>
          {showAdvanced && (
            <div className="mt-2">
              <label className="mb-1 block text-xs font-medium text-slate-600">שם הגיליון בקובץ (אם ידוע)</label>
              <Input
                value={sheetName}
                onChange={(e) => setSheetName(e.target.value)}
                placeholder="לדוגמה: גידרון — אם לא יוזן, המערכת תזהה בעצמה"
              />
            </div>
          )}
        </div>
      )}

      <div className="flex justify-center">
        <Button onClick={handleUpload} disabled={!file || upload.isPending} className="px-8">
          {upload.isPending ? "מעלה..." : "התחל ניתוח חכם"}
        </Button>
      </div>
    </div>
  );
}
