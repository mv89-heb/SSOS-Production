"use client";
import { useMemo, useState } from "react";
import { Loader2, Search, AlertCircle, AlertTriangle, ArrowUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useImportPreview, useImportValidationDetails } from "@/hooks/use-imports";
import { countAdditionalOffersForRow } from "@/lib/offer-counting";
import { ImportPreviewRow, PreviewAction } from "@/types";

const ACTION_LABELS: Record<PreviewAction, string> = {
  CREATE: "יצירה",
  UPDATE: "עדכון",
  SKIP: "דילוג (ללא שינוי)",
  EXISTING: "קיים",
  ERROR: "שגיאה",
};

const ACTION_STYLES: Record<PreviewAction, string> = {
  CREATE: "bg-green-100 text-green-700",
  UPDATE: "bg-blue-100 text-blue-700",
  SKIP: "bg-slate-100 text-slate-500",
  EXISTING: "bg-slate-100 text-slate-500",
  ERROR: "bg-red-100 text-red-700",
};

type SortKey = "row_number" | "product_name" | "price";

interface PreviewStepProps {
  sessionId: number;
  onNext: () => void;
  onBack: () => void;
}

export function PreviewStep({ sessionId, onNext, onBack }: PreviewStepProps) {
  const { data: preview, isLoading } = useImportPreview(sessionId);
  const { data: validationDetails } = useImportValidationDetails(sessionId);

  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<"all" | PreviewAction>("all");
  const [sortKey, setSortKey] = useState<SortKey>("row_number");
  const [sortAsc, setSortAsc] = useState(true);

  const issuesByRow = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const issue of validationDetails?.issues ?? []) {
      if (issue.row_number == null) continue;
      const list = map.get(issue.row_number) ?? [];
      list.push(issue.message);
      map.set(issue.row_number, list);
    }
    return map;
  }, [validationDetails]);

  const rows = preview?.rows ?? [];

  const filtered = useMemo(() => {
    let result = rows;
    if (actionFilter !== "all") {
      result = result.filter((r) => r.product_action === actionFilter);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (r) =>
          (r.product_name ?? "").toLowerCase().includes(q) ||
          (r.supplier_name ?? "").toLowerCase().includes(q) ||
          (r.category ?? "").toLowerCase().includes(q)
      );
    }
    const sorted = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "row_number") cmp = a.row_number - b.row_number;
      else if (sortKey === "product_name") cmp = (a.product_name ?? "").localeCompare(b.product_name ?? "");
      else if (sortKey === "price") cmp = (a.price ?? 0) - (b.price ?? 0);
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [rows, actionFilter, search, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">שלב 5: תצוגה מקדימה</h2>
        <p className="text-sm text-slate-500">כל שורה בקובץ ומה שיקרה לה בפועל בייבוא.</p>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 p-6 text-sm text-slate-500">
          <Loader2 className="animate-spin" size={16} />
          טוען תצוגה מקדימה...
        </div>
      )}

      {preview && (
        <>
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input
                placeholder="חיפוש לפי מוצר, ספק או קטגוריה..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={actionFilter} onChange={(e) => setActionFilter(e.target.value as typeof actionFilter)} className="w-44">
              <option value="all">כל הפעולות</option>
              {Object.entries(ACTION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>

          <p className="text-xs text-slate-400">
            מציג {filtered.length} מתוך {rows.length} שורות
          </p>

          <div className="max-h-[420px] overflow-auto rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50">
                <tr className="border-b border-slate-100 text-xs text-slate-500">
                  <th className="p-3 text-start">
                    <button onClick={() => toggleSort("row_number")} className="flex items-center gap-1">
                      שורה <ArrowUpDown size={11} />
                    </button>
                  </th>
                  <th className="p-3 text-start">
                    <button onClick={() => toggleSort("product_name")} className="flex items-center gap-1">
                      מוצר <ArrowUpDown size={11} />
                    </button>
                  </th>
                  <th className="p-3 text-start">ספק</th>
                  <th className="p-3 text-start">יחידה</th>
                  <th className="p-3 text-start">קטגוריה</th>
                  <th className="p-3 text-start">
                    <button onClick={() => toggleSort("price")} className="flex items-center gap-1">
                      מחיר <ArrowUpDown size={11} />
                    </button>
                  </th>
                  <th className="p-3 text-start">פעולה</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row: ImportPreviewRow) => {
                  const messages = issuesByRow.get(row.row_number) ?? [];
                  return (
                    <tr key={row.id} className="border-b border-slate-50 last:border-0">
                      <td className="p-3 text-slate-400">{row.row_number}</td>
                      <td className="p-3">
                        <div className="font-medium text-slate-900">{row.product_name ?? "—"}</div>
                        {messages.length > 0 && (
                          <div className="mt-1 space-y-0.5">
                            {messages.map((m, i) => (
                              <div
                                key={i}
                                className={`flex items-start gap-1 text-xs ${row.has_errors ? "text-red-600" : "text-amber-600"}`}
                              >
                                {row.has_errors ? <AlertCircle size={11} className="mt-0.5 shrink-0" /> : <AlertTriangle size={11} className="mt-0.5 shrink-0" />}
                                <span>{m}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {countAdditionalOffersForRow(row) > 0 && (
                          <div className="mt-1 text-xs text-slate-400">
                            + {countAdditionalOffersForRow(row)} הצעות מחיר נוספות
                          </div>
                        )}
                      </td>
                      <td className="p-3 text-slate-600">{row.supplier_name ?? "—"}</td>
                      <td className="p-3 text-slate-600">{row.unit ?? "—"}</td>
                      <td className="p-3 text-slate-600">{row.category ?? "—"}</td>
                      <td className="p-3 text-slate-900">{row.price != null ? row.price.toLocaleString() : "—"}</td>
                      <td className="p-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${ACTION_STYLES[row.product_action]}`}>
                          {ACTION_LABELS[row.product_action]}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          חזרה לבדיקת תקינות
        </Button>
        <Button onClick={onNext} disabled={!preview}>
          המשך לתוכנית ייבוא
        </Button>
      </div>
    </div>
  );
}
