"use client";
import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, ChevronDown, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useImportSession, useAnalyzeImport, useImportAnalysis } from "@/hooks/use-imports";

const FORMAT_PLAIN_LABELS: Record<string, string> = {
  WIDE: "כמה ספקים מוצגים באותה טבלה",
  TALL: "ספק אחד לכל הטבלה",
  MIXED: "מבנה מעורב",
  UNKNOWN: "מבנה לא סטנדרטי",
};

interface ScanStepProps {
  sessionId: number;
  onScanned: () => void;
  onBack: () => void;
}

function ChecklistItem({ delay, children }: { delay: number; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div
      className={cn(
        "flex items-center gap-2 text-sm text-slate-700 transition-all duration-300",
        visible ? "translate-y-0 opacity-100" : "translate-y-1 opacity-0"
      )}
    >
      <CheckCircle2 className="shrink-0 text-green-500" size={16} />
      {children}
    </div>
  );
}

export function ScanStep({ sessionId, onScanned, onBack }: ScanStepProps) {
  const { data: session } = useImportSession(sessionId);
  const analyzeMutation = useAnalyzeImport(sessionId);
  const { data: analysis } = useImportAnalysis(sessionId);
  const [showTechnical, setShowTechnical] = useState(false);

  useEffect(() => {
    if (session && session.workbook_sheet_count == null && !analyzeMutation.isPending && !analyzeMutation.isSuccess) {
      analyzeMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id, session?.workbook_sheet_count]);

  const results = analyzeMutation.data ?? analysis;
  const stagedSheet = results?.find((s) => s.sheet_name === session?.staged_sheet_name);
  const isAnalyzing = analyzeMutation.isPending || (!results && session?.workbook_sheet_count == null);

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-slate-900">ניתוח חכם</h2>
        <p className="mt-1 text-sm text-slate-500">{session?.filename}</p>
      </div>

      {isAnalyzing && (
        <div className="flex flex-col items-center gap-3 py-10">
          <Loader2 className="animate-spin text-primary" size={32} />
          <p className="text-sm text-slate-500">מנתח את הקובץ...</p>
        </div>
      )}

      {analyzeMutation.isError && (
        <p className="text-center text-sm text-red-500">
          {(analyzeMutation.error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
            "הניתוח נכשל."}
        </p>
      )}

      {results && session && stagedSheet && (
        <div className="space-y-5">
          <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Sparkles className="text-primary" size={16} />
              מה המערכת מצאה
            </div>
            <div className="space-y-2.5">
              <ChecklistItem delay={0}>
                נמצאו <strong>{session.workbook_sheet_count}</strong> גיליונות בקובץ
              </ChecklistItem>
              {stagedSheet.detected_suppliers.length > 0 && (
                <ChecklistItem delay={150}>
                  זוהו <strong>{stagedSheet.detected_suppliers.length}</strong> ספקים:{" "}
                  {stagedSheet.detected_suppliers.map((s) => s.header).join(", ")}
                </ChecklistItem>
              )}
              <ChecklistItem delay={300}>
                נמצאו כ-<strong>{stagedSheet.row_count}</strong> מוצרים בגיליון "{stagedSheet.sheet_name}"
              </ChecklistItem>
              <ChecklistItem delay={450}>
                מבנה הטבלה: <strong>{FORMAT_PLAIN_LABELS[stagedSheet.detected_format]}</strong>
              </ChecklistItem>
              {(stagedSheet.header_tier_count ?? 1) > 1 && (
                <ChecklistItem delay={600}>
                  זוהתה כותרת מורכבת (מספר שורות כותרת) — טופל אוטומטית
                </ChecklistItem>
              )}
              {stagedSheet.has_merged_header_cells && (
                <ChecklistItem delay={750}>תאים ממוזגים בכותרת — טופל אוטומטית</ChecklistItem>
              )}
            </div>
          </div>

          <div>
            <button
              onClick={() => setShowTechnical((v) => !v)}
              className="flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-slate-600"
            >
              <ChevronDown size={14} className={cn("transition-transform", showTechnical && "rotate-180")} />
              פרטים טכניים למתקדמים
            </button>
            {showTechnical && (
              <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-slate-500">
                      <th className="p-2 text-start">עמודה</th>
                      <th className="p-2 text-start">זוהה כ-</th>
                      <th className="p-2 text-start">ביטחון</th>
                      <th className="p-2 text-start">דוגמה</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stagedSheet.columns
                      .filter((c) => !c.header.startsWith("עמודה"))
                      .map((c) => (
                        <tr key={c.index} className="border-b border-slate-50 last:border-0">
                          <td className="p-2 font-medium text-slate-900">{c.header}</td>
                          <td className="p-2 text-slate-600">{c.detected_type}</td>
                          <td className="p-2 text-slate-500">{c.confidence}</td>
                          <td className="p-2 text-slate-400">{c.sample_values.slice(0, 2).join(", ")}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                {results.length > 1 && (
                  <p className="border-t border-slate-100 p-2 text-xs text-slate-400">
                    בקובץ יש {results.length - 1} גיליונות נוספים שלא נטענו — כדי לייבא גיליון אחר, חזור לשלב הקודם
                    והעלה שוב תוך ציון שם הגיליון (באפשרויות המתקדמות).
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          חזרה
        </Button>
        <Button onClick={onScanned} disabled={!results || analyzeMutation.isPending}>
          המשך
        </Button>
      </div>
    </div>
  );
}
