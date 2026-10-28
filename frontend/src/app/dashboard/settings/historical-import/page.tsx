"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Archive, CheckCircle2, FileText, Loader2, ScanText, ShieldAlert } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { documentIntelligenceService, type DocumentAnalysis } from "@/services/document-intelligence-service";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";

type HistoricalDocument = {
  id: number; analysis_id: number; document_type: string; source_filename: string | null;
  supplier_id: number | null; supplier_name: string | null; document_number: string | null;
  document_date: string | null; currency: string; total_amount: number | null;
  order_reference: string | null; needs_review: boolean; review_reasons: string[];
  duplicate_of_id: number | null; historical_order_id: number | null;
  extracted_data: Record<string, any>;
};
type HistoricalOrder = {
  id: number; supplier_name: string; order_reference: string | null; order_date: string | null;
  currency: string; total_amount: number | null; document_count: number; historical_only: boolean;
};
type Batch = {
  id: number; name: string; status: string; document_count: number; order_count: number;
  documents?: HistoricalDocument[]; orders?: HistoricalOrder[]; created_at: string | null;
};
type Progress = { name: string; stage: string; percent: number; error?: string };
type Draft = { supplier_name: string; document_number: string; document_date: string; order_reference: string; confirm_duplicate: boolean; confirm_extraction: boolean };

const typeLabel: Record<string, string> = { INVOICE: "חשבונית", DELIVERY_NOTE: "תעודת משלוח" };
const reasonLabel: Record<string, string> = {
  supplier_not_identified: "הספק לא זוהה",
  document_number_missing: "חסר מספר מסמך",
  document_date_missing_or_invalid: "תאריך חסר או לא תקין",
  multiple_supplier_sections_require_review: "זוהו כמה ספקים במסמך",
  no_line_items_extracted: "לא זוהו שורות פריטים",
  possible_duplicate: "חשד לכפילות",
  historical_order_reference_not_set: "לא שויך להזמנה היסטורית",
};

export default function HistoricalImportPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [batchName, setBatchName] = useState("");
  const [batch, setBatch] = useState<Batch | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [scans, setScans] = useState<DocumentAnalysis[]>([]);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const canManage = permissions.canManageImports(user);
  const addedAnalysisIds = useMemo(() => new Set((batch?.documents ?? []).map((doc) => doc.analysis_id)), [batch?.documents]);

  async function refreshBatch(id: number) {
    const { data } = await apiClient.get<{ success: boolean; batch: Batch }>(`/api/historical-document-import/batches/${id}`);
    setBatch(data.batch);
    const nextDrafts: Record<number, Draft> = {};
    for (const doc of data.batch.documents ?? []) {
      nextDrafts[doc.id] = {
        supplier_name: doc.supplier_name ?? "",
        document_number: doc.document_number ?? "",
        document_date: doc.document_date ?? "",
        order_reference: doc.order_reference ?? "",
        confirm_duplicate: !doc.review_reasons?.includes("possible_duplicate"),
        confirm_extraction: !(doc.review_reasons ?? []).some((reason) => ["multiple_supplier_sections_require_review", "no_line_items_extracted"].includes(reason)),
      };
    }
    setDrafts((current) => ({ ...nextDrafts, ...current }));
  }

  useEffect(() => {
    if (!canManage) return;
    apiClient.get<{ success: boolean; batches: Batch[] }>("/api/historical-document-import/batches")
      .then(({ data }) => setBatches(data.batches))
      .catch(() => setError("לא ניתן לטעון אצוות ייבוא קודמות."));
  }, [canManage]);

  if (!canManage) return <div className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">נדרשת הרשאת מנהל כדי להשתמש בייבוא היסטורי.</div>;

  async function startScan() {
    if (!files.length) { setError("בחר קובצי PDF או תמונות לסריקה."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      let activeBatch = batch;
      if (!activeBatch) {
        const { data } = await apiClient.post<{ success: boolean; batch: Batch }>("/api/historical-document-import/batches", { name: batchName.trim() || undefined });
        activeBatch = data.batch;
        setBatch(activeBatch);
      }
      setProgress(files.map((file) => ({ name: file.name, stage: "ממתין לסריקה", percent: 0 })));
      const results = await documentIntelligenceService.uploadManyAndAnalyze(files, (file, analysis, stage, percent, errorText) => {
        setProgress((current) => current.map((item) => item.name === file.name ? { ...item, stage: stage === "done" ? "הסתיים" : stage === "failed" ? "נכשל" : stage === "processing" ? "מנתח" : stage === "uploaded" ? "הועלה" : "מעלה", percent, error: errorText } : item));
        if (analysis) setScans((current) => {
          const next = current.filter((item) => item.id !== analysis.id);
          return [...next, analysis];
        });
      });
      setScans((current) => {
        const byId = new Map(current.map((item) => [item.id, item]));
        results.forEach((item) => byId.set(item.id, item));
        return [...byId.values()];
      });
      setFiles([]);
      setMessage(`הסריקה הסתיימה. ${results.filter((item) => ["ANALYZED", "PARTIALLY_APPLIED", "APPLIED"].includes(item.status)).length} מסמכים נותחו בהצלחה. יש לבדוק כל מסמך לפני קליטה היסטורית.`);
      if (activeBatch) await refreshBatch(activeBatch.id);
    } catch (e: unknown) {
      const ex = e as { response?: { data?: { message?: string } }; message?: string };
      setError(ex.response?.data?.message ?? ex.message ?? "הסריקה נכשלה.");
    } finally { setBusy(false); }
  }

  async function addToBatch(analysis: DocumentAnalysis) {
    if (!batch) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const ref = (analysis.extracted_data as any)?.document_number ?? "";
      await apiClient.post(`/api/historical-document-import/batches/${batch.id}/documents`, { analysis_id: analysis.id, order_reference: ref });
      await refreshBatch(batch.id);
      setMessage(`המסמך ${analysis.filename} נוסף לאצווה. יש להשלים את בדיקת הנתונים והשייכות להזמנה.`);
    } catch (e: unknown) {
      const ex = e as { response?: { data?: { message?: string } }; message?: string };
      setError(ex.response?.data?.message ?? ex.message ?? "הוספת המסמך נכשלה.");
    } finally { setBusy(false); }
  }

  async function saveReview(doc: HistoricalDocument) {
    if (!batch) return;
    const draft = drafts[doc.id];
    if (!draft) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiClient.patch(`/api/historical-document-import/batches/${batch.id}/documents/${doc.id}`, {
        supplier_name: draft.supplier_name,
        document_number: draft.document_number,
        document_date: draft.document_date,
        order_reference: draft.order_reference,
        confirm_duplicate: draft.confirm_duplicate,
        confirm_extraction: draft.confirm_extraction,
      });
      await refreshBatch(batch.id);
      setMessage("בדיקת המסמך נשמרה.");
    } catch (e: unknown) {
      const ex = e as { response?: { data?: { message?: string } }; message?: string };
      setError(ex.response?.data?.message ?? ex.message ?? "שמירת הבדיקה נכשלה.");
    } finally { setBusy(false); }
  }

  async function finalize() {
    if (!batch) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiClient.post(`/api/historical-document-import/batches/${batch.id}/finalize`, {});
      await refreshBatch(batch.id);
      const { data } = await apiClient.get<{ success: boolean; batches: Batch[] }>("/api/historical-document-import/batches");
      setBatches(data.batches);
      setMessage("האצווה נקלטה כתיעוד היסטורי. לא נוצרו הזמנות פעילות ולא בוצעו תנועות מלאי, תשלומים או התראות.");
    } catch (e: unknown) {
      const ex = e as { response?: { data?: { message?: string } }; message?: string };
      setError(ex.response?.data?.message ?? ex.message ?? "סיום הייבוא נכשל.");
    } finally { setBusy(false); }
  }

  return <div className="space-y-6" dir="rtl">
    <div className="flex items-center gap-3">
      <button onClick={() => router.push("/dashboard/settings")} aria-label="חזרה להגדרות" className="text-slate-400 hover:text-slate-700"><ArrowRight size={20} /></button>
      <div><h1 className="text-2xl font-bold text-slate-900">ייבוא היסטורי מרוכז</h1><p className="mt-1 text-sm text-slate-500">סריקת חשבוניות ותעודות משלוח מהעבר ויצירת הזמנות היסטוריות מבודדות.</p></div>
    </div>

    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
      <div className="flex items-start gap-2"><ShieldAlert size={20} className="mt-0.5 shrink-0" /><div><strong>מצב היסטורי בלבד</strong><p className="mt-1">המערכת שומרת את המידע שחולץ, לא את קובצי המקור. הזמנות שייווצרו כאן נשמרות באזור היסטורי נפרד ואינן משפיעות על מלאי, הזמנות פעילות, תשלומים או תזכורות.</p></div></div>
    </div>

    <section className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-bold"><ScanText size={20} /> 1. סריקת אצווה</h2>
      <label className="block space-y-1 text-sm"><span className="font-semibold">שם האצווה (אופציונלי)</span><input value={batchName} onChange={(e) => setBatchName(e.target.value)} disabled={Boolean(batch)} maxLength={200} placeholder="לדוגמה: מסמכי ספקים 2023–2025" className="w-full rounded-lg border px-3 py-2 disabled:bg-slate-50 sm:max-w-xl" /></label>
      <label className="block space-y-1 text-sm"><span className="font-semibold">קובצי מקור לסריקה</span><input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.svg,application/pdf,image/*" disabled={busy || batch?.status === "finalized"} onChange={(e) => setFiles(Array.from(e.target.files ?? []))} className="block w-full rounded-lg border p-2 sm:max-w-xl" /><span className="text-xs text-slate-500">אפשר לבחור הרבה קבצים בבת אחת. הקבצים מעובדים זמנית לצורך חילוץ הנתונים ולא נשמרים כקבצים מצורפים.</span></label>
      <button onClick={startScan} disabled={busy || files.length === 0 || batch?.status === "finalized"} className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{busy ? <Loader2 size={16} className="animate-spin" /> : <ScanText size={16} />} {busy ? "מעבד..." : "סריקה וניתוח של כל הקבצים"}</button>
      {progress.length > 0 && <div className="space-y-2">{progress.map((item) => <div key={item.name} className="rounded-lg border p-3 text-sm"><div className="flex justify-between gap-3"><span className="break-all font-medium">{item.name}</span><span>{item.stage} · {item.percent}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-100"><div className="h-full bg-indigo-600" style={{ width: `${item.percent}%` }} /></div>{item.error && <p className="mt-1 text-xs text-red-600">{item.error}</p>}</div>)}</div>}
    </section>

    {scans.length > 0 && <section className="space-y-3 rounded-2xl border bg-white p-5 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-bold"><FileText size={20} /> 2. מסמכים שנסרקו</h2>
      <p className="text-sm text-slate-500">הוסיפו לאצווה רק חשבוניות ותעודות משלוח. מסמכים שלא זוהו נכון יישארו מחוץ לאצווה עד לבדיקה.</p>
      {scans.map((scan) => {
        const extracted = scan.extracted_data ?? {};
        const type = String(extracted.document_type ?? scan.document_type ?? "").toUpperCase();
        const supported = ["INVOICE", "DELIVERY_NOTE", "DELIVERY NOTE"].includes(type);
        const alreadyAdded = addedAnalysisIds.has(scan.id);
        return <div key={scan.id} className="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0"><div className="break-all font-semibold">{scan.filename}</div><div className="mt-1 text-sm text-slate-500">{typeLabel[type] ?? type ?? "סוג לא זוהה"} · {scan.status}</div><div className="mt-1 text-sm">{extracted.supplier?.name || "ספק לא זוהה"} · מס׳ {extracted.document_number || "חסר"} · {extracted.document_date || "תאריך חסר"} · {extracted.totals?.total != null ? `${extracted.totals.total} ${extracted.currency || "ILS"}` : "סכום לא זוהה"}</div>{scan.error_message && <p className="mt-1 text-xs text-red-600">{scan.error_message}</p>}</div>
          <button onClick={() => addToBatch(scan)} disabled={busy || !batch || alreadyAdded || !supported || !["ANALYZED", "PARTIALLY_APPLIED", "APPLIED"].includes(scan.status)} className="shrink-0 rounded-lg border px-3 py-2 text-sm font-bold disabled:opacity-40">{alreadyAdded ? "נוסף לאצווה" : "הוסף לאצווה"}</button>
        </div>;
      })}
    </section>}

    {batch && <section className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">3. בדיקה ויצירת הזמנות היסטוריות</h2><p className="text-sm text-slate-500">אצווה #{batch.id} · {batch.name} · {batch.document_count} מסמכים · {batch.order_count} הזמנות היסטוריות · {batch.status === "finalized" ? "הושלמה" : "ממתינה לבדיקה"}</p></div>{batch.status !== "finalized" && <button onClick={finalize} disabled={busy || !batch.documents?.length || batch.documents.some((doc) => doc.needs_review)} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-40">{busy ? "שומר..." : "אשר ויצור הזמנות היסטוריות"}</button>}</div>
      {(batch.documents ?? []).length === 0 && <p className="rounded-lg border border-dashed p-4 text-sm text-slate-500">עדיין לא נוספו מסמכים לאצווה.</p>}
      {(batch.documents ?? []).map((doc) => {
        const draft = drafts[doc.id] ?? { supplier_name: doc.supplier_name ?? "", document_number: doc.document_number ?? "", document_date: doc.document_date ?? "", order_reference: doc.order_reference ?? "", confirm_duplicate: false, confirm_extraction: false };
        return <div key={doc.id} className="space-y-3 rounded-xl border p-4">
          <div className="flex flex-wrap justify-between gap-2"><div className="font-bold">{typeLabel[doc.document_type] ?? doc.document_type} · {doc.source_filename || `מסמך ${doc.id}`}</div><span className={doc.needs_review ? "text-sm font-bold text-amber-700" : "text-sm font-bold text-emerald-700"}>{doc.needs_review ? "נדרשת בדיקה" : "נבדק"}</span></div>
          {doc.review_reasons?.length > 0 && <p className="text-sm text-amber-800">{doc.review_reasons.map((reason) => reasonLabel[reason] ?? reason).join(" · ")}</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="space-y-1 text-xs"><span>שם ספק</span><input value={draft.supplier_name} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, supplier_name: e.target.value } }))} disabled={batch.status === "finalized"} className="w-full rounded border px-2 py-2 text-sm" /></label>
            <label className="space-y-1 text-xs"><span>מספר מסמך</span><input value={draft.document_number} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, document_number: e.target.value } }))} disabled={batch.status === "finalized"} className="w-full rounded border px-2 py-2 text-sm" /></label>
            <label className="space-y-1 text-xs"><span>תאריך מסמך</span><input type="date" value={draft.document_date} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, document_date: e.target.value } }))} disabled={batch.status === "finalized"} className="w-full rounded border px-2 py-2 text-sm" /></label>
            <label className="space-y-1 text-xs"><span>אסמכתת הזמנה היסטורית — זהה במסמכים קשורים</span><input value={draft.order_reference} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, order_reference: e.target.value } }))} disabled={batch.status === "finalized"} placeholder="למשל: רכש-2024-018" className="w-full rounded border px-2 py-2 text-sm" /></label>
          </div>
          {doc.review_reasons?.includes("possible_duplicate") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.confirm_duplicate} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, confirm_duplicate: e.target.checked } }))} disabled={batch.status === "finalized"} />בדקתי את החשד לכפילות ואישרתי לכלול את המסמך</label>}
          {(doc.review_reasons?.includes("multiple_supplier_sections_require_review") || doc.review_reasons?.includes("no_line_items_extracted")) && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.confirm_extraction} onChange={(e) => setDrafts((s) => ({ ...s, [doc.id]: { ...draft, confirm_extraction: e.target.checked } }))} disabled={batch.status === "finalized"} />בדקתי ידנית את פרטי המסמך והשורות שחולצו</label>}
          {batch.status !== "finalized" && <div className="flex justify-end"><button onClick={() => saveReview(doc)} disabled={busy} className="rounded-lg border px-3 py-2 text-sm font-bold disabled:opacity-50">שמור בדיקה</button></div>}
          {doc.extracted_data?.items?.length > 0 && <details><summary className="cursor-pointer text-sm font-semibold">הצג {doc.extracted_data.items.length} שורות שחולצו</summary><div className="mt-2 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-right"><th className="p-2">פריט</th><th className="p-2">כמות</th><th className="p-2">מחיר יחידה</th></tr></thead><tbody>{doc.extracted_data.items.map((item: any, index: number) => <tr key={index} className="border-b"><td className="p-2">{item.description || "ללא תיאור"}</td><td className="p-2">{item.quantity ?? "—"}</td><td className="p-2">{item.unit_price ?? "—"}</td></tr>)}</tbody></table></div></details>}
        </div>;
      })}
      {(batch.orders ?? []).length > 0 && <div className="space-y-2 border-t pt-4"><h3 className="font-bold">הזמנות היסטוריות שנוצרו</h3>{batch.orders?.map((order) => <div key={order.id} className="flex flex-wrap justify-between gap-2 rounded-lg bg-slate-50 p-3 text-sm"><div><strong>#{order.id} · {order.supplier_name}</strong><div className="text-slate-500">{order.order_reference || "ללא אסמכתה"} · {order.order_date || "ללא תאריך"} · {order.document_count} מסמכים</div></div><div className="font-bold">{order.total_amount == null ? "סכום לא ידוע" : `${order.total_amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} ${order.currency}`}</div></div>)}</div>}
    </section>}

    {batches.length > 0 && <section className="rounded-2xl border bg-white p-5 shadow-sm"><h2 className="mb-3 font-bold">אצוות קודמות</h2><div className="space-y-2">{batches.map((item) => <button key={item.id} onClick={async () => { setError(""); try { await refreshBatch(item.id); } catch { setError("טעינת האצווה נכשלה."); } }} className="flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-right hover:bg-slate-50"><span><strong>#{item.id} · {item.name}</strong><span className="mr-2 text-xs text-slate-500">{item.document_count} מסמכים · {item.order_count} הזמנות</span></span><span className="text-xs">{item.status === "finalized" ? "הושלמה" : "ממתינה לבדיקה"}</span></button>)}</div></section>}

    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
  </div>;
}
