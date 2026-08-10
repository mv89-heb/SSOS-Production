"use client";
import { useState } from "react";
import { Loader2, PackageCheck, Truck, Tag, AlertTriangle, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useCommitImport, useImportPreview } from "@/hooks/use-imports";
import { computeOfferBreakdown } from "@/lib/offer-counting";
import { ImportValidation, ImportExecution } from "@/types";

interface PlanImportStepProps {
  sessionId: number;
  validation: ImportValidation;
  onImported: (execution: ImportExecution) => void;
  onBack: () => void;
}

function PlanRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-white p-3">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Icon size={16} className="text-slate-400" />
        {label}
      </div>
      <span className="text-lg font-semibold text-slate-900">{value}</span>
    </div>
  );
}

export function PlanImportStep({ sessionId, validation, onImported, onBack }: PlanImportStepProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const commit = useCommitImport(sessionId);
  // Same /preview-based, backend-unchanged calculation as ValidationStep —
  // see lib/offer-counting.ts for why the raw validation.summary.offers.created
  // count is misleading (it includes each row's own primary listing).
  const { data: preview } = useImportPreview(sessionId);
  const breakdown = computeOfferBreakdown(preview?.rows);

  const handleConfirmImport = () => {
    setError(null);
    commit.mutate(undefined, {
      onSuccess: (execution) => {
        setConfirmOpen(false);
        onImported(execution);
      },
      onError: (err) => {
        const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
        setError(message || "הייבוא נכשל.");
        setConfirmOpen(false);
      },
    });
  };

  const { summary } = validation;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">שלב 6: תוכנית ייבוא</h2>
        <p className="text-sm text-slate-500">סיכום סופי לפני כתיבה בפועל למערכת. הכתיבה תתבצע רק לאחר אישור.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <PlanRow icon={Truck} label="ספקים חדשים" value={summary.suppliers.created} />
        <PlanRow icon={PackageCheck} label="מוצרים חדשים" value={summary.products.created} />
        <PlanRow icon={PackageCheck} label="מוצרים לעדכון" value={summary.products.updated} />
        <PlanRow icon={DollarSign} label="רשומות מחיר שזוהו" value={breakdown.priceRecordsDetected} />
        <PlanRow icon={DollarSign} label="מחירי ספק ראשיים" value={breakdown.primarySupplierPrices} />
        <PlanRow icon={Tag} label="הצעות מחיר נוספות שייווצרו" value={breakdown.additionalSupplierOffers} />
        <PlanRow icon={PackageCheck} label="שורות ללא שינוי" value={summary.products.skipped} />
        <PlanRow icon={AlertTriangle} label="שורות עם שגיאה (ידולגו)" value={summary.errors} />
      </div>

      {summary.errors > 0 && (
        <p className="text-xs text-amber-600">
          {summary.errors} שורות עם שגיאות לא ייכנסו למערכת בייבוא הזה — כל שאר הנתונים כן יובאו.
        </p>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          חזרה לתצוגה מקדימה
        </Button>
        <Button onClick={() => setConfirmOpen(true)} disabled={commit.isPending}>
          {commit.isPending ? "מייבא..." : "ביצוע הייבוא"}
        </Button>
      </div>

      <Modal open={confirmOpen} onClose={() => !commit.isPending && setConfirmOpen(false)} title="אישור ייבוא">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            פעולה זו תיצור {summary.suppliers.created} ספקים, {summary.products.created} מוצרים חדשים,
            תעדכן {summary.products.updated} מוצרים קיימים, ותוסיף {breakdown.additionalSupplierOffers} הצעות מחיר
            מספקים חלופיים — ישירות במערכת. הפעולה ניתנת לביטול (Rollback) לאחר מכן.
          </p>
          {commit.isPending && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="animate-spin" size={16} />
              מבצע ייבוא, נא להמתין...
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)} disabled={commit.isPending}>
              ביטול
            </Button>
            <Button onClick={handleConfirmImport} disabled={commit.isPending}>
              {commit.isPending ? "מייבא..." : "אישור וייבוא"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
