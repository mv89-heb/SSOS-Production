"use client";
import { useState } from "react";
import { CheckCircle2, Download, RotateCcw, Truck, PackageCheck, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useRollbackExecution } from "@/hooks/use-imports";
import { ImportExecution, ImportSession } from "@/types";

interface ReportStepProps {
  session: ImportSession | undefined;
  execution: ImportExecution;
  onStartOver: () => void;
}

function ReportStat({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-4 text-center">
      <Icon className="mx-auto mb-1 text-primary" size={20} />
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

export function ReportStep({ session, execution, onStartOver }: ReportStepProps) {
  const [rollbackOpen, setRollbackOpen] = useState(false);
  const [rolledBack, setRolledBack] = useState(execution.status === "ROLLED_BACK");
  const rollback = useRollbackExecution();

  const handleRollback = () => {
    rollback.mutate(execution.id, {
      onSuccess: () => {
        setRolledBack(true);
        setRollbackOpen(false);
      },
    });
  };

  const handleDownloadReport = () => {
    const lines = [
      `דוח ייבוא — ${session?.filename ?? ""}`,
      `תאריך: ${new Date(execution.executed_at).toLocaleString("he-IL")}`,
      `סטטוס: ${rolledBack ? "בוטל (Rollback)" : "הושלם"}`,
      "",
      `ספקים שנוצרו: ${execution.summary.suppliers_created}`,
      `מוצרים שנוצרו: ${execution.summary.products_created}`,
      `מוצרים שעודכנו: ${execution.summary.products_updated}`,
      `הצעות מחיר שנוצרו: ${execution.summary.offers_created}`,
      "",
      `שורות שדולגו: ${execution.skipped_rows.length}`,
      ...execution.skipped_rows.map((s) => `  שורה ${s.row_number}: ${s.reason}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `import-report-${execution.id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col items-center gap-2 py-4 text-center">
        {rolledBack ? (
          <>
            <RotateCcw className="text-slate-400" size={40} />
            <h2 className="text-lg font-semibold text-slate-900">הייבוא בוטל</h2>
            <p className="text-sm text-slate-500">כל הרשומות שנוצרו על ידי הייבוא הזה הוסרו, והמחירים שעודכנו שוחזרו.</p>
          </>
        ) : (
          <>
            <CheckCircle2 className="text-green-500" size={40} />
            <h2 className="text-lg font-semibold text-slate-900">שלב 8: דוח סיום — הייבוא הושלם</h2>
            <p className="text-sm text-slate-500">{session?.filename}</p>
          </>
        )}
      </div>

      {!rolledBack && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ReportStat icon={Truck} label="ספקים נוצרו" value={execution.summary.suppliers_created} />
          <ReportStat icon={PackageCheck} label="מוצרים נוצרו" value={execution.summary.products_created} />
          <ReportStat icon={PackageCheck} label="מוצרים עודכנו" value={execution.summary.products_updated} />
          <ReportStat icon={Tag} label="הצעות מחיר נוצרו" value={execution.summary.offers_created} />
        </div>
      )}

      {execution.skipped_rows.length > 0 && !rolledBack && (
        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
          <p className="mb-1 text-sm font-medium text-amber-800">{execution.skipped_rows.length} שורות דולגו</p>
          <ul className="max-h-32 space-y-0.5 overflow-y-auto text-xs text-amber-700">
            {execution.skipped_rows.map((s, i) => (
              <li key={i}>
                שורה {s.row_number}: {s.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap justify-between gap-2">
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleDownloadReport}>
            <Download size={16} />
            הורדת דוח
          </Button>
          {!rolledBack && (
            <Button variant="danger" onClick={() => setRollbackOpen(true)}>
              <RotateCcw size={16} />
              ביטול הייבוא (Rollback)
            </Button>
          )}
        </div>
        <Button onClick={onStartOver}>ייבוא קובץ נוסף</Button>
      </div>

      <Modal open={rollbackOpen} onClose={() => setRollbackOpen(false)} title="ביטול הייבוא">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            פעולה זו תמחק את כל {execution.summary.products_created} המוצרים ו-{execution.summary.suppliers_created} הספקים
            שנוצרו על ידי הייבוא הזה, ותשחזר את המחיר הקודם ב-{execution.summary.products_updated} מוצרים שעודכנו.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRollbackOpen(false)} disabled={rollback.isPending}>
              ביטול
            </Button>
            <Button variant="danger" onClick={handleRollback} disabled={rollback.isPending}>
              {rollback.isPending ? "מבטל..." : "אישור ביטול הייבוא"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
