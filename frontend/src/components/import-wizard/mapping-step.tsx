"use client";
import { useState } from "react";
import { Loader2, CheckCircle2, Save, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import {
  useImportMapping, useUpdateMapping, useApproveMapping,
  useSaveTemplate, useApplyTemplate,
} from "@/hooks/use-imports";
import { useSuppliers } from "@/hooks/use-catalog";
import { MappingDecision } from "@/services/import-service";
import { MappingTarget, PriceType } from "@/types";

const TARGET_LABELS: Record<MappingTarget, string> = {
  PRODUCT_NAME: "שם מוצר",
  PRODUCT_CODE: "קוד מוצר",
  BARCODE: "ברקוד",
  CATEGORY: "קטגוריה",
  UNIT: "יחידת מידה",
  SUPPLIER_NAME: "שם ספק",
  SUPPLIER_CODE: "קוד ספק",
  PRICE: "מחיר",
  PRICE_BEFORE_VAT: "מחיר לפני מע\"מ",
  PRICE_AFTER_VAT: "מחיר אחרי מע\"מ",
  DISCOUNT_PRICE: "מחיר לאחר הנחה",
  SUPPLIER_OFFER: "הצעת מחיר לספק",
  IGNORE: "התעלם",
};

const PRICE_TYPE_LABELS: Record<PriceType, string> = {
  regular: "רגיל",
  before_vat: "לפני מע\"מ",
  after_vat: "אחרי מע\"מ",
  discount: "הנחה",
};

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-orange-100 text-orange-700",
  none: "bg-slate-100 text-slate-500",
};

interface MappingStepProps {
  sessionId: number;
  onApproved: () => void;
  onBack: () => void;
}

export function MappingStep({ sessionId, onApproved, onBack }: MappingStepProps) {
  const { data, isLoading } = useImportMapping(sessionId);
  const updateMapping = useUpdateMapping(sessionId);
  const approveMapping = useApproveMapping(sessionId);
  const saveTemplate = useSaveTemplate(sessionId);
  const applyTemplate = useApplyTemplate(sessionId);
  const { data: suppliers } = useSuppliers();

  const [templateName, setTemplateName] = useState("");
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mapping = data?.mapping;
  const templates = data?.matching_templates ?? [];

  const columns = (mapping?.columns ?? []).filter((c) => !c.column_header.startsWith("עמודה"));

  const submitDecision = (decision: MappingDecision) => {
    setError(null);
    updateMapping.mutate([decision], {
      onError: (err) => {
        const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
        setError(message || "עדכון המיפוי נכשל.");
      },
    });
  };

  const handleApprove = () => {
    setError(null);
    approveMapping.mutate(undefined, {
      onSuccess: onApproved,
      onError: (err) => {
        const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
        setError(message || "אישור המיפוי נכשל.");
      },
    });
  };

  const handlePrimaryAction = () => {
    if (mapping?.status === "APPROVED") {
      onApproved();
      return;
    }
    handleApprove();
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 p-6 text-sm text-slate-500">
        <Loader2 className="animate-spin" size={16} />
        טוען מיפוי...
      </div>
    );
  }

  if (!mapping) {
    return <p className="text-sm text-red-500">לא נמצא מיפוי לסשן זה.</p>;
  }

  const unreviewedCount = columns.filter((c) => !c.user_reviewed).length;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">שלב 3: מיפוי עמודות</h2>
        <p className="text-sm text-slate-500">
          המערכת הציעה מיפוי אוטומטי לכל עמודה. ניתן לאשר או לשנות כל שורה.
        </p>
      </div>

      {templates.length > 0 && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Sparkles className="text-primary" size={16} />
            נמצאו תבניות מיפוי קודמות
          </div>
          <div className="space-y-2">
            {templates.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
                <div className="text-sm">
                  <span className="font-medium text-slate-900">{t.name}</span>
                  {t.supplier_name && <span className="text-slate-500"> · {t.supplier_name}</span>}
                </div>
                <Button
                  variant="secondary"
                  className="text-xs"
                  onClick={() => applyTemplate.mutate(t.id)}
                  disabled={applyTemplate.isPending}
                >
                  החל תבנית
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-xs text-slate-500">
              <th className="p-3 text-start">עמודה בקובץ</th>
              <th className="p-3 text-start">הצעת המערכת</th>
              <th className="p-3 text-start">שדה יעד</th>
              <th className="p-3 text-start">ספק</th>
              <th className="p-3 text-start">סוג מחיר</th>
              <th className="p-3 text-start">סטטוס</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col) => {
              const needsSupplier = col.final_target === "SUPPLIER_OFFER" || col.final_target === "SUPPLIER_NAME";
              const needsPriceType = col.final_target === "SUPPLIER_OFFER";
              return (
                <tr key={col.column_index} className="border-b border-slate-50 last:border-0">
                  <td className="p-3 font-medium text-slate-900">{col.column_header}</td>
                  <td className="p-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${CONFIDENCE_STYLES[col.suggested_confidence]}`}>
                      {TARGET_LABELS[col.suggested_target]}
                    </span>
                  </td>
                  <td className="p-3">
                    <Select
                      value={col.final_target}
                      onChange={(e) =>
                        submitDecision({ column_index: col.column_index, target: e.target.value as MappingTarget })
                      }
                      className="min-w-[140px]"
                    >
                      {Object.entries(TARGET_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="p-3">
                    {needsSupplier ? (
                      <Select
                        value={col.final_supplier_id ?? ""}
                        onChange={(e) =>
                          submitDecision({
                            column_index: col.column_index,
                            supplier_id: e.target.value ? Number(e.target.value) : null,
                            supplier_name: e.target.value ? undefined : col.final_supplier_name || col.column_header,
                          })
                        }
                        className="min-w-[130px]"
                      >
                        <option value="">
                          {col.final_supplier_name ? `חדש: ${col.final_supplier_name}` : "בחר ספק..."}
                        </option>
                        {suppliers?.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="p-3">
                    {needsPriceType ? (
                      <Select
                        value={col.final_price_type ?? ""}
                        onChange={(e) =>
                          submitDecision({ column_index: col.column_index, price_type: e.target.value as PriceType })
                        }
                        className="min-w-[110px]"
                      >
                        <option value="">בחר...</option>
                        {Object.entries(PRICE_TYPE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="p-3">
                    {col.user_reviewed ? (
                      <span className="flex items-center gap-1 text-xs text-green-600">
                        <CheckCircle2 size={12} />
                        נבדק
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">הצעה בלבד</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {unreviewedCount > 0 && (
        <p className="text-xs text-slate-400">{unreviewedCount} עמודות עדיין לא נבדקו ידנית — יאושרו לפי הצעת המערכת.</p>
      )}

      {mapping.status === "APPROVED" ? (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 p-3 text-sm text-green-700">
          <CheckCircle2 size={16} />
          המיפוי אושר
        </div>
      ) : showSaveTemplate ? (
        <div className="flex items-end gap-2 rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-slate-700">שם התבנית</label>
            <Input value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="לדוגמה: מיפוי גידרון" />
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              if (!templateName.trim()) return;
              saveTemplate.mutate(
                { name: templateName.trim() },
                { onSuccess: () => setShowSaveTemplate(false) }
              );
            }}
            disabled={saveTemplate.isPending || !templateName.trim()}
          >
            שמירה
          </Button>
          <Button variant="ghost" onClick={() => setShowSaveTemplate(false)}>
            ביטול
          </Button>
        </div>
      ) : (
        <button
          onClick={() => setShowSaveTemplate(true)}
          className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          <Save size={14} />
          שמור מיפוי זה כתבנית לשימוש עתידי
        </button>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          חזרה
        </Button>
        <Button onClick={handlePrimaryAction} disabled={approveMapping.isPending}>
          {approveMapping.isPending ? "מאשר..." : mapping.status === "APPROVED" ? "המשך לבדיקת תקינות" : "אישור מיפוי והמשך"}
        </Button>
      </div>
    </div>
  );
}
