"use client";
import { useEffect } from "react";
import { Loader2, AlertTriangle, XCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useValidateImport, useImportSession, useImportPreview } from "@/hooks/use-imports";
import { computeOfferBreakdown } from "@/lib/offer-counting";
import { ImportValidation } from "@/types";

interface ValidationStepProps {
  sessionId: number;
  onValidated: (validation: ImportValidation) => void;
  onBack: () => void;
}

function StatCard({ value, label, tone = "default" }: { value: number; label: string; tone?: "default" | "warning" | "error" }) {
  const color = tone === "warning" ? "text-amber-600" : tone === "error" ? "text-red-600" : "text-slate-900";
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

export function ValidationStep({ sessionId, onValidated, onBack }: ValidationStepProps) {
  const { data: session } = useImportSession(sessionId);
  const validateMutation = useValidateImport(sessionId);
  const validation = validateMutation.data;
  // Fetching the same /preview data already used in Step 5, to compute an
  // accurate offer breakdown here too — no backend change, see
  // lib/offer-counting.ts.
  const { data: preview } = useImportPreview(sessionId, validateMutation.isSuccess);
  const breakdown = computeOfferBreakdown(preview?.rows);

  useEffect(() => {
    if (session && !validateMutation.isPending && !validateMutation.isSuccess) {
      validateMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">שלב 4: בדיקת תקינות</h2>
        <p className="text-sm text-slate-500">בדיקת מוצרים קיימים, ספקים קיימים, כפילויות, מחירים ונתונים חסרים.</p>
      </div>

      {validateMutation.isPending && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 p-6 text-sm text-slate-500">
          <Loader2 className="animate-spin" size={16} />
          בודק את הנתונים...
        </div>
      )}

      {validateMutation.isError && (
        <p className="text-sm text-red-500">
          {(validateMutation.error as { response?: { data?: { message?: string } } })?.response?.data?.message ||
            "בדיקת התקינות נכשלה."}
        </p>
      )}

      {validation && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard value={validation.summary.products.created} label="מוצרים חדשים" />
            <StatCard value={validation.summary.products.updated} label="מוצרים לעדכון" />
            <StatCard value={validation.summary.warnings} label="אזהרות" tone="warning" />
            <StatCard value={validation.summary.errors} label="שגיאות" tone="error" />
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-slate-500">פירוט מחירים</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatCard value={breakdown.priceRecordsDetected} label="רשומות מחיר שזוהו" />
              <StatCard value={breakdown.primarySupplierPrices} label="מחירי ספק ראשיים" />
              <StatCard value={breakdown.additionalSupplierOffers} label="הצעות מחיר נוספות שייווצרו" />
            </div>
          </div>

          {validation.summary.errors > 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <XCircle size={16} className="mt-0.5 shrink-0" />
              <span>
                נמצאו {validation.summary.errors} שגיאות. השורות הבעייתיות ידולגו אוטומטית בזמן הייבוא ולא ייכנסו למערכת —
                שאר השורות התקינות יובאו כרגיל. ניתן לראות את הפירוט המלא בשלב הבא (תצוגה מקדימה).
              </span>
            </div>
          )}

          {validation.summary.warnings > 0 && validation.summary.errors === 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>נמצאו {validation.summary.warnings} אזהרות — לא חוסמות את הייבוא, כדאי לעיין בהן בשלב הבא.</span>
            </div>
          )}

          {validation.summary.errors === 0 && validation.summary.warnings === 0 && (
            <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
              <CheckCircle2 size={16} />
              כל הנתונים תקינים.
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          חזרה למיפוי
        </Button>
        <Button onClick={() => validation && onValidated(validation)} disabled={!validation || validateMutation.isPending}>
          המשך לתצוגה מקדימה
        </Button>
      </div>
    </div>
  );
}
