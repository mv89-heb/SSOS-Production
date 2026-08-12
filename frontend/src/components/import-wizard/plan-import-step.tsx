"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  DollarSign,
  Loader2,
  PackageCheck,
  Search,
  Tag,
  Truck,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import {
  useCommitImport,
  useImportPreview,
  useImportValidationDetails,
} from "@/hooks/use-imports";
import { computeOfferBreakdown } from "@/lib/offer-counting";
import { ImportExecution, ImportIssue, ImportPreviewRow, ImportValidation } from "@/types";

interface PlanImportStepProps {
  sessionId: number;
  validation: ImportValidation;
  onImported: (execution: ImportExecution) => void;
  onBack: () => void;
}

function PlanRow({
  icon: Icon,
  label,
  value,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-lg border border-slate-100 bg-white p-3 text-right transition hover:border-slate-200 hover:bg-slate-50 ${
        onClick ? "cursor-pointer" : "cursor-default"
      }`}
    >
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Icon size={16} className="text-slate-400" />
        {label}
      </div>
      <span className="text-lg font-semibold text-slate-900">{value}</span>
    </button>
  );
}

function actionLabel(action: ImportPreviewRow["product_action"]): string {
  switch (action) {
    case "CREATE":
      return "מוצר חדש";
    case "UPDATE":
      return "עדכון מוצר קיים";
    case "SKIP":
      return "ללא שינוי";
    case "ERROR":
      return "שגיאה — ידולג";
    default:
      return action;
  }
}

function reasonForRow(row: ImportPreviewRow, issues: ImportIssue[]): string {
  const rowIssues = issues.filter((issue) => issue.row_number === row.row_number);
  const errors = rowIssues.filter((issue) => issue.severity === "ERROR");
  if (errors.length) return errors.map((issue) => issue.message).join(" • ");

  if (row.product_action === "CREATE") {
    const supplier = row.supplier_name
      ? row.matched_supplier_id
        ? `הספק "${row.supplier_name}" קיים`
        : `הספק "${row.supplier_name}" חדש וייווצר`
      : "לא זוהה ספק";
    return `לא נמצא מוצר תואם במערכת; ${supplier}; המחיר ${row.price ?? "—"}`;
  }

  if (row.product_action === "UPDATE") {
    return `נמצא מוצר קיים (ID ${row.matched_product_id ?? "—"}); המחיר יעודכן מ־${row.old_price ?? "—"} ל־${row.price ?? "—"}`;
  }

  if (row.product_action === "SKIP") {
    return "נמצא מוצר קיים והמחיר/הנתונים הרלוונטיים אינם דורשים שינוי";
  }

  return "השורה אינה ניתנת לייבוא";
}

function DetailRow({ row, issues }: { row: ImportPreviewRow; issues: ImportIssue[] }) {
  const rowIssues = issues.filter((issue) => issue.row_number === row.row_number);
  const hasError = rowIssues.some((issue) => issue.severity === "ERROR") || row.has_errors;
  const hasWarning = rowIssues.some((issue) => issue.severity === "WARNING") || row.has_warnings;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">שורה {row.row_number}</span>
          <span
            className={`rounded px-2 py-1 text-xs font-medium ${
              hasError
                ? "bg-red-50 text-red-700"
                : row.product_action === "CREATE"
                  ? "bg-blue-50 text-blue-700"
                  : row.product_action === "UPDATE"
                    ? "bg-amber-50 text-amber-700"
                    : "bg-slate-100 text-slate-600"
            }`}
          >
            {actionLabel(row.product_action)}
          </span>
          {hasWarning && !hasError && <AlertTriangle size={15} className="text-amber-500" />}
        </div>
        <span className="font-medium text-slate-900">{row.product_name || "ללא שם מוצר"}</span>
      </div>

      <div className="mt-2 grid gap-1 text-xs text-slate-600 sm:grid-cols-2">
        <div>ספק: <b>{row.supplier_name || "לא זוהה"}</b></div>
        <div>מחיר: <b>{row.price ?? "לא זוהה"}</b>{row.old_price != null ? ` (ישן: ${row.old_price})` : ""}</div>
        <div>יחידה: <b>{row.unit || "לא הוגדרה"}</b></div>
        <div>קטגוריה: <b>{row.category || "לא הוגדרה"}</b></div>
      </div>

      <p className={`mt-2 text-sm ${hasError ? "text-red-700" : "text-slate-600"}`}>
        <span className="font-medium">סיבה:</span> {reasonForRow(row, issues)}
      </p>

      {rowIssues.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-slate-100 pt-2">
          {rowIssues.map((issue) => (
            <div key={issue.id} className="flex gap-2 text-xs">
              {issue.severity === "ERROR" ? (
                <XCircle size={14} className="mt-0.5 shrink-0 text-red-500" />
              ) : (
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
              )}
              <span className={issue.severity === "ERROR" ? "text-red-700" : "text-amber-700"}>
                <b>{issue.code}</b>: {issue.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {row.offers && row.offers.length > 0 && (
        <div className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-600">
          <span className="font-medium">מחירי ספקים שזוהו:</span>{" "}
          {row.offers.map((offer, index) => (
            <span key={`${offer.supplier_name}-${index}`} className="mr-2 inline-block">
              {offer.supplier_name}: {offer.price}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function PlanImportStep({ sessionId, validation, onImported, onBack }: PlanImportStepProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"ALL" | "ERROR" | "CREATE" | "UPDATE" | "SKIP">("ALL");
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);

  const commit = useCommitImport(sessionId);
  const { data: preview, isLoading: previewLoading } = useImportPreview(sessionId);
  const { data: validationDetails } = useImportValidationDetails(sessionId, true);
  const breakdown = computeOfferBreakdown(preview?.rows);
  const issues = validationDetails?.issues ?? validation.issues ?? [];
  const rows = preview?.rows ?? [];

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesFilter =
        filter === "ALL" ||
        (filter === "ERROR" ? row.has_errors || row.product_action === "ERROR" : row.product_action === filter);
      const haystack = `${row.row_number} ${row.product_name ?? ""} ${row.supplier_name ?? ""}`.toLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
  }, [rows, filter, search]);

  const visibleRows = showAll ? filteredRows : filteredRows.slice(0, 50);
  const { summary } = validation;

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

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-900">למה כל מספר כזה?</h3>
            <p className="text-xs text-slate-500">הפירוט מבוסס על תוצאות ה־Validation וה־Preview, לא על ניחוש.</p>
          </div>
          {previewLoading && <Loader2 size={17} className="animate-spin text-slate-400" />}
        </div>

        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg bg-white p-3"><b>{summary.products.created}</b> מוצרים חדשים — לא נמצא עבורם מוצר תואם במערכת.</div>
          <div className="rounded-lg bg-white p-3"><b>{summary.products.updated}</b> מוצרים לעדכון — נמצא מוצר תואם והמחיר החדש שונה מהמחיר הקיים.</div>
          <div className="rounded-lg bg-white p-3"><b>{summary.suppliers.created}</b> ספקים חדשים — לא נמצא ספק תואם והם ייווצרו בעת הייבוא.</div>
          <div className="rounded-lg bg-white p-3"><b>{breakdown.additionalSupplierOffers}</b> הצעות נוספות — מחירי ספק שאינם המחיר הראשי של אותה שורה.</div>
          <div className="rounded-lg bg-white p-3"><b>{summary.products.skipped}</b> שורות ללא שינוי — המוצר קיים והמחיר הרלוונטי כבר תואם.</div>
          <div className="rounded-lg bg-red-50 p-3 text-red-700"><b>{summary.errors}</b> שורות עם שגיאה — קיימת לפחות שגיאת Validation חוסמת, ולכן הן ידולגו.</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="font-semibold text-slate-900">פירוט שורה־שורה</h3>
              <p className="text-xs text-slate-500">כל שורה מציגה מה יקרה לה ולמה.</p>
            </div>
            <div className="relative sm:w-72">
              <Search size={15} className="absolute right-3 top-2.5 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="חפש מוצר, ספק או מספר שורה"
                className="w-full rounded-md border border-slate-200 py-2 pl-3 pr-9 text-sm outline-none focus:border-slate-400"
              />
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {(["ALL", "ERROR", "CREATE", "UPDATE", "SKIP"] as const).map((value) => {
              const labels = { ALL: "הכול", ERROR: "שגיאות", CREATE: "חדשים", UPDATE: "לעדכון", SKIP: "ללא שינוי" };
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilter(value)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium ${filter === value ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600"}`}
                >
                  {labels[value]}
                </button>
              );
            })}
          </div>
        </div>

        <div className="max-h-[560px] space-y-2 overflow-auto p-3">
          {visibleRows.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-500">לא נמצאו שורות לפי הסינון.</div>
          ) : (
            visibleRows.map((row) => <DetailRow key={row.id || row.row_number} row={row} issues={issues} />)
          )}
        </div>

        {filteredRows.length > 50 && (
          <button
            type="button"
            onClick={() => setShowAll((value) => !value)}
            className="flex w-full items-center justify-center gap-2 border-t border-slate-100 p-3 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            {showAll ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {showAll ? "הצג פחות" : `הצג את כל ${filteredRows.length} השורות`}
          </button>
        )}
      </div>

      {summary.errors > 0 && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          <XCircle size={17} className="mt-0.5 shrink-0" />
          <div>
            <b>{summary.errors} שורות עם שגיאות לא ייכנסו למערכת.</b>
            <div className="mt-1">פתח את מסנן "שגיאות" למעלה כדי לראות לכל שורה את הסיבה המדויקת ואת קוד השגיאה.</div>
          </div>
        </div>
      )}

      {summary.errors === 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
          <CheckCircle2 size={17} /> אין שורות עם שגיאה חוסמת.
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>חזרה לתצוגה מקדימה</Button>
        <Button onClick={() => setConfirmOpen(true)} disabled={commit.isPending || previewLoading || summary.errors === rows.length}>
          {commit.isPending ? "מייבא..." : "ביצוע הייבוא"}
        </Button>
      </div>

      <Modal open={confirmOpen} onClose={() => !commit.isPending && setConfirmOpen(false)} title="אישור ייבוא">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            הפעולה תיצור <b>{summary.suppliers.created}</b> ספקים, תיצור <b>{summary.products.created}</b> מוצרים,
            תעדכן <b>{summary.products.updated}</b> מוצרים ותיצור <b>{breakdown.additionalSupplierOffers}</b> הצעות מחיר נוספות.
            {summary.errors > 0 && <> {summary.errors} שורות עם שגיאות <b>ידולגו</b> ולא ייכתבו למערכת.</>}
          </p>
          <p className="text-xs text-slate-500">לפני האישור ניתן לעבור על כל השורות ולראות את הסיבה לפעולה, כולל פירוט השגיאות.</p>
          {commit.isPending && (
            <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="animate-spin" size={16} /> מבצע ייבוא, נא להמתין...</div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)} disabled={commit.isPending}>ביטול</Button>
            <Button onClick={handleConfirmImport} disabled={commit.isPending}>{commit.isPending ? "מייבא..." : "אישור וייבוא"}</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
