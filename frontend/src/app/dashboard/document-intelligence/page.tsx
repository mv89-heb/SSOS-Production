"use client";

import { useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileSearch, Loader2, Sparkles, Upload } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useProducts, useSuppliers } from "@/hooks/use-catalog";
import { documentIntelligenceService, type DocumentAnalysis, type ExtractedItem } from "@/services/document-intelligence-service";

const statusLabel: Record<string, string> = { UPLOADED: "הועלה", PROCESSING: "מנתח...", ANALYZED: "נותח — מוכן לבדיקה", AI_UNAVAILABLE: "Gemini אינו מוגדר", FAILED: "הניתוח נכשל", APPLIED: "יושם בהצלחה" };
const allowed = ".pdf,.png,.jpg,.jpeg,.webp,.svg";

type Mapping = { product?: number; supplier?: number; update?: boolean };

export default function DocumentIntelligencePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const { data: products = [] } = useProducts(undefined, true);
  const { data: suppliers = [] } = useSuppliers(true);
  const [analyses, setAnalyses] = useState<DocumentAnalysis[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mappings, setMappings] = useState<Record<number, Mapping>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const analysis = analyses.find((item) => item.id === selectedId) ?? analyses[analyses.length - 1] ?? null;
  const items = useMemo<ExtractedItem[]>(() => Array.isArray(analysis?.extracted_data?.items) ? analysis.extracted_data.items : [], [analysis]);

  async function handleFiles(fileList: FileList | null) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setBusy(true); setError("");
    try {
      const results = await documentIntelligenceService.uploadManyAndAnalyze(files);
      setAnalyses((current) => [...results, ...current]);
      setSelectedId(results[0]?.id ?? null);
    } catch (err: any) {
      setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן להעלות או לנתח את המסמכים");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function analyzeAgain() {
    if (!analysis) return;
    setBusy(true); setError("");
    try { const result = await documentIntelligenceService.analyze(analysis.id); setAnalyses((all) => all.map((item) => item.id === result.id ? result : item)); }
    catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "הניתוח נכשל"); }
    finally { setBusy(false); }
  }

  async function apply() {
    if (!analysis || !items.length) return;
    const lines = items.map((item, index) => { const map = mappings[index] || {}; return { product_id: map.product, supplier_id: map.supplier, price: Number(item.unit_price), currency: analysis.extracted_data?.currency || "ILS", unit: item.unit, package_quantity: item.package_quantity, update_price: Boolean(map.update), match_method: "MANUAL_REVIEW" }; });
    if (lines.some((line) => !line.product_id || !line.supplier_id || !Number.isFinite(line.price) || line.price <= 0)) { setError("יש לבחור מוצר וספק לכל שורה ולוודא שמחיר השורה תקין."); return; }
    setBusy(true); setError("");
    try { const result = await documentIntelligenceService.apply(analysis.id, lines); setAnalyses((all) => all.map((item) => item.id === result.id ? result : item)); await queryClient.invalidateQueries({ queryKey: ["products"] }); }
    catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן ליישם את הנתונים"); }
    finally { setBusy(false); }
  }

  const setMap = (index: number, patch: Mapping) => setMappings((current) => ({ ...current, [index]: { ...current[index], ...patch } }));

  return <div dir="rtl" className="space-y-6 pb-10">
    <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div><div className="mb-2 flex items-center gap-2 text-indigo-600"><Sparkles size={18}/><span className="text-sm font-semibold">Gemini Document Intelligence</span></div><h1 className="text-3xl font-bold">ניתוח מסמכים עם Gemini</h1><p className="mt-1 text-sm text-slate-500">העלה מסמך אחד או כמה מסמכים יחד. נתונים לא משתנים בלי אישור שלך.</p></div>
        <button type="button" onClick={() => inputRef.current?.click()} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-bold text-white shadow-lg disabled:opacity-50"><Upload size={18}/> העלאת מסמכים</button>
        <input ref={inputRef} type="file" multiple accept={allowed} className="hidden" onChange={(event) => handleFiles(event.target.files)} />
      </div>
      <p className="mt-3 text-xs text-slate-400">PDF, PNG, JPG, WEBP ו-SVG · ניתן לבחור מספר קבצים בבת אחת</p>
    </header>

    {error && <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-700"><AlertTriangle size={18}/>{error}</div>}

    {analyses.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">מסמכים שהועלו ({analyses.length})</h2></div><div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3">{analyses.map((item) => <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`rounded-xl border p-3 text-right ${item.id === analysis?.id ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/30" : "border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"}`}><div className="truncate font-semibold">{item.filename}</div><div className="mt-1 text-xs text-slate-500">{statusLabel[item.status] || item.status}</div></button>)}</div></section>}

    {!analysis && <section className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-14 text-center dark:border-slate-700 dark:bg-slate-950"><FileSearch className="mx-auto mb-4 text-slate-400" size={44}/><h2 className="text-xl font-bold">אין מסמכים לניתוח</h2><p className="mt-2 text-sm text-slate-500">בחר מסמך אחד או כמה מסמכים כדי להתחיל.</p></section>}

    {analysis && <>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-wrap items-center gap-3"><div className="rounded-xl bg-indigo-50 p-3 text-indigo-600"><FileSearch size={22}/></div><div className="min-w-0 flex-1"><div className="truncate font-bold">{analysis.filename}</div><div className="text-sm text-slate-500">{analysis.document_type || "מסמך"} · {analysis.provider || "—"} {analysis.model ? `· ${analysis.model}` : ""}</div></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{statusLabel[analysis.status] || analysis.status}</span>{(analysis.status === "FAILED" || analysis.status === "AI_UNAVAILABLE") && <button type="button" onClick={analyzeAgain} disabled={busy} className="rounded-lg border px-3 py-2 text-sm font-bold">נסה שוב</button>}</div>{analysis.error_message && <p className="mt-3 text-sm text-red-600">{analysis.error_message}</p>}</section>
      {analysis.status === "ANALYZED" && <><section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[["ספק", analysis.extracted_data?.supplier?.name],["מספר מסמך", analysis.extracted_data?.document_number],["תאריך", analysis.extracted_data?.document_date],["סה״כ", analysis.extracted_data?.totals?.total != null ? `${analysis.extracted_data.totals.total} ${analysis.extracted_data.currency || "ILS"}` : "—"]].map(([label,value]) => <div key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-bold">{value || "—"}</div></div>)}</section>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">בדיקה ואישור שורות</h2><p className="mt-1 text-xs text-slate-500">Gemini לא משנה נתונים בעצמו. בחר מוצר וספק לכל שורה.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50 text-right text-xs text-slate-500 dark:bg-slate-900"><tr><th className="p-3">פריט</th><th className="p-3">כמות</th><th className="p-3">מחיר</th><th className="p-3">מוצר במערכת</th><th className="p-3">ספק</th><th className="p-3">עדכון מחיר</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{items.map((item,index) => <tr key={index}><td className="max-w-[260px] p-3"><div className="font-medium">{item.description || "ללא תיאור"}</div><div className="text-xs text-slate-400">מק״ט: {item.supplier_sku || "—"} · ברקוד: {item.barcode || "—"}</div></td><td className="p-3">{item.quantity ?? "—"} {item.unit || ""}</td><td className="p-3 font-bold">{item.unit_price ?? "—"} {analysis.extracted_data?.currency || "ILS"}</td><td className="p-3"><select className="w-56 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900" value={mappings[index]?.product || ""} onChange={(e) => setMap(index,{product:Number(e.target.value)})}><option value="">בחר מוצר...</option>{products.map((p)=><option key={p.id} value={p.id}>{p.name}{p.sku ? ` · ${p.sku}` : ""}</option>)}</select></td><td className="p-3"><select className="w-52 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900" value={mappings[index]?.supplier || ""} onChange={(e) => setMap(index,{supplier:Number(e.target.value)})}><option value="">בחר ספק...</option>{suppliers.map((s)=><option key={s.id} value={s.id}>{s.name}</option>)}</select></td><td className="p-3 text-center"><input type="checkbox" checked={Boolean(mappings[index]?.update)} onChange={(e)=>setMap(index,{update:e.target.checked})} aria-label="עדכן מחיר"/></td></tr>)}</tbody></table></div><div className="flex flex-col gap-3 border-t border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800"><span className="text-xs text-slate-500">{items.length} שורות חולצו</span><button type="button" onClick={apply} disabled={busy || !items.length} className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-bold text-white disabled:opacity-50">{busy ? <Loader2 className="animate-spin" size={18}/> : <CheckCircle2 size={18}/>}אשר ויישם</button></div></section></>}
      {analysis.status === "APPLIED" && <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 font-bold text-emerald-700"><CheckCircle2/> המסמך יושם בהצלחה.</div>}
    </>}
  </div>;
}
