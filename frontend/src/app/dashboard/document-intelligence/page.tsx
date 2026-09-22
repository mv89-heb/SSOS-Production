"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, FileSearch, Loader2, Sparkles, Upload } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useProducts, useSuppliers } from "@/hooks/use-catalog";
import { documentIntelligenceService, type DocumentAnalysis, type ExtractedItem, type SupplierSection } from "@/services/document-intelligence-service";

const statusLabel: Record<string, string> = { UPLOADED: "הועלה", PROCESSING: "מנתח...", ANALYZED: "נותח — מוכן לבדיקה", AI_UNAVAILABLE: "Gemini אינו מוגדר", FAILED: "הניתוח נכשל", APPLIED: "יושם בהצלחה" };
const allowed = ".pdf,.png,.jpg,.jpeg,.webp,.svg";
type Mapping = { product?: number; supplier?: number; update?: boolean };
type UploadProgress = { name: string; stage: "uploading" | "uploaded" | "processing" | "done"; percent: number; status?: string; error?: string; eta?: number | null; elapsed?: number; pages?: string };

function formatSeconds(value: number | null | undefined) { if (value == null || !Number.isFinite(value)) return "—"; const seconds = Math.max(0, Math.round(value)); if (seconds < 60) return `${seconds} שנ׳`; const minutes = Math.floor(seconds / 60); return `${minutes}:${String(seconds % 60).padStart(2, "0")} דק׳`; }
function supplierLabel(section: SupplierSection | undefined) { return section?.supplier?.name || "ספק לא מזוהה — נדרשת בדיקה"; }

function SearchableSelect({ value, onChange, options, placeholder }: { value: number | string; onChange: (value: number) => void; options: Array<{ id: number; name: string; extra?: string | null }>; placeholder: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => { if (!rootRef.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const selected = options.find((option) => option.id === Number(value));
  const filtered = options.filter((option) => `${option.name} ${option.extra || ""}`.toLocaleLowerCase("he").includes(query.trim().toLocaleLowerCase("he")));
  return <div ref={rootRef} className="relative w-56">
    <button type="button" onClick={() => setOpen((current) => !current)} className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-right dark:border-slate-700 dark:bg-slate-900">
      <span className={selected ? "truncate" : "truncate text-slate-400"}>{selected ? `${selected.name}${selected.extra ? ` · ${selected.extra}` : ""}` : placeholder}</span>
      <span className="mr-2 text-xs text-slate-400">⌄</span>
    </button>
    {open && <div className="absolute right-0 z-50 mt-1 w-full rounded-xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-950">
      <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="חיפוש..." className="mb-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none dark:border-slate-700 dark:bg-slate-900" />
      <div className="max-h-64 overflow-y-auto">
        {filtered.length ? filtered.map((option) => <button key={option.id} type="button" onClick={() => { onChange(option.id); setOpen(false); setQuery(""); }} className="block w-full rounded-lg px-3 py-2 text-right text-sm hover:bg-slate-100 dark:hover:bg-slate-800">{option.name}{option.extra ? ` · ${option.extra}` : ""}</button>) : <div className="px-3 py-3 text-sm text-slate-400">לא נמצאו תוצאות</div>}
      </div>
    </div>}
  </div>;
}

export default function DocumentIntelligencePage() {
  const inputRef = useRef<HTMLInputElement>(null); const queryClient = useQueryClient();
  const { data: products = [] } = useProducts(undefined, true); const { data: suppliers = [] } = useSuppliers(true);
  const [analyses, setAnalyses] = useState<DocumentAnalysis[]>([]); const [selectedId, setSelectedId] = useState<number | null>(null); const [mappings, setMappings] = useState<Record<number, Mapping>>({}); const [progress, setProgress] = useState<UploadProgress[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (!busy) return; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [busy]);
  const analysis = analyses.find((item) => item.id === selectedId) ?? analyses[analyses.length - 1] ?? null;
  const data = analysis?.extracted_data;
  const productOptions = useMemo(() => [...products].sort((a, b) => a.name.localeCompare(b.name, "he")).map((p) => ({ id: p.id, name: p.name, extra: p.sku })), [products]);
  const supplierOptions = useMemo(() => [...suppliers].sort((a, b) => a.name.localeCompare(b.name, "he")).map((s) => ({ id: s.id, name: s.name, extra: s.customer_number })), [suppliers]);
  const items = useMemo<ExtractedItem[]>(() => Array.isArray(data?.items) ? data.items : [], [data]);
  const sections = useMemo<SupplierSection[]>(() => Array.isArray(data?.supplier_sections) ? data.supplier_sections : [], [data]);
  const updateProgress = (file: File, patch: Partial<UploadProgress>) => setProgress((current) => current.map((item) => item.name === file.name ? { ...item, ...patch } : item));

  async function handleFiles(fileList: FileList | null) {
    const files = Array.from(fileList || []); if (!files.length) return; setBusy(true); setError(""); setProgress(files.map((file) => ({ name: file.name, stage: "uploading", percent: 0 })));
    try {
      const results = await documentIntelligenceService.uploadManyAndAnalyze(files, (file, item, stage, percent) => {
        const p = item?.extracted_data?.processing;
        updateProgress(file, { stage, percent: p?.percent ?? percent, status: item?.status, error: item?.error_message || undefined, eta: p?.eta_seconds, elapsed: p?.elapsed_seconds, pages: p?.pages_total ? `${p.pages_processed || 0}/${p.pages_total} עמודים` : undefined });
        if (item) { setAnalyses((current) => current.some((row) => row.id === item.id) ? current.map((row) => row.id === item.id ? item : row) : [item, ...current]); setSelectedId(item.id); }
      });
      setAnalyses((current) => { const incoming = new Map(results.map((item) => [item.id, item])); return [...results, ...current.filter((item) => !incoming.has(item.id))]; }); setSelectedId(results[0]?.id ?? null); setProgress((current) => current.map((item) => ({ ...item, stage: "done", percent: 100 })));
    } catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן להעלות או לנתח את המסמכים"); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function apply() {
    if (!analysis || !items.length) return;
    const lines = items.map((item, index) => {
      const map = mappings[index] || {};
      const product = item.product_matching?.best_match;
      const supplier = item.supplier_matching;
      const autoProduct = product && (product.decision === "AUTO_MATCH" || ((product.confidence || 0) >= 0.75 && product.decision !== "LOW_CONFIDENCE")) ? product.product_id : undefined;
      const autoSupplier = supplier?.decision === "AUTO_MATCH" ? supplier.supplier_id : undefined;
      const numericPrice = Number(item.unit_price);
      const autoUpdatePrice = Boolean(autoProduct && autoSupplier && Number.isFinite(numericPrice) && numericPrice > 0);
      return { product_id: map.product || autoProduct, supplier_id: map.supplier || autoSupplier, price: Number.isFinite(numericPrice) && numericPrice > 0 ? numericPrice : undefined, currency: data?.currency || "ILS", unit: item.unit, package_quantity: item.package_quantity, update_price: map.update ?? autoUpdatePrice, match_method: product?.method || "MANUAL_REVIEW", match_confidence: product?.confidence };
    });
    const unresolved = lines.map((line, index) => (!line.product_id || !line.supplier_id ? items[index]?.description || `שורה ${index + 1}` : null)).filter(Boolean); if (unresolved.length) { setError(`יש עדיין ${unresolved.length} שורות ללא התאמה בטוחה: ${unresolved.slice(0, 3).join(", ")}${unresolved.length > 3 ? " ועוד..." : ""}. בחר מוצר/ספק רק עבור שורות אלה.`); return; }
    setBusy(true); setError(""); try { const result = await documentIntelligenceService.apply(analysis.id, lines); setAnalyses((all) => all.map((item) => item.id === result.id ? result : item)); await queryClient.invalidateQueries({ queryKey: ["products"] }); } catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן ליישם את הנתונים"); } finally { setBusy(false); }
  }

  const setMap = (index: number, patch: Mapping) => setMappings((current) => ({ ...current, [index]: { ...current[index], ...patch } }));
  const defaultProduct = (item: ExtractedItem, index: number) => { const match = item.product_matching?.best_match; const auto = match && (match.decision === "AUTO_MATCH" || ((match.confidence || 0) >= 0.75 && match.decision !== "LOW_CONFIDENCE")); return mappings[index]?.product || (auto ? match?.product_id || "" : ""); };
  const defaultSupplier = (item: ExtractedItem, index: number) => mappings[index]?.supplier || (item.supplier_matching?.decision === "AUTO_MATCH" ? item.supplier_matching.supplier_id || "" : "");

  return <div dir="rtl" className="space-y-6 pb-10">
    <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between"><div><div className="mb-2 flex items-center gap-2 text-indigo-600"><Sparkles size={18}/><span className="text-sm font-semibold">Gemini Document Intelligence</span></div><h1 className="text-3xl font-bold">ניתוח מסמכים עם Gemini</h1><p className="mt-1 text-sm text-slate-500">העלה מסמך אחד או כמה מסמכים. המערכת מזהה ספקים מרובים ומקשרת כל שורת מוצר לספק שלה.</p></div><button type="button" onClick={() => inputRef.current?.click()} disabled={busy} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-bold text-white shadow-lg disabled:opacity-50"><Upload size={18}/> העלאת מסמכים</button><input ref={inputRef} type="file" multiple accept={allowed} className="hidden" onChange={(event) => handleFiles(event.target.files)} /></div><p className="mt-3 text-xs text-slate-400">PDF, PNG, JPG, WEBP ו-SVG · גם מספר ספקים באותו קובץ נתמכים</p></header>

    {progress.length > 0 && <section className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5 shadow-sm dark:border-indigo-900 dark:bg-indigo-950/20"><div className="mb-4 flex items-center justify-between"><h2 className="font-bold">התקדמות מסמכים</h2>{busy && <Loader2 className="animate-spin text-indigo-600" size={18}/>}</div><div className="space-y-4">{progress.map((item) => { const live = analyses.find((a) => a.filename === item.name)?.extracted_data?.processing; const percent = live?.percent ?? item.percent; const eta = live?.eta_seconds ?? item.eta; const elapsed = live?.elapsed_seconds ?? item.elapsed; const pages = live?.pages_total ? `${live.pages_processed || 0}/${live.pages_total} עמודים` : item.pages; return <div key={item.name} className="rounded-xl border border-white/80 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"><div className="flex items-center gap-3"><div className="min-w-0 flex-1"><div className="truncate font-semibold">{item.name}</div><div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">{item.stage === "uploading" ? <span>מעלה מסמך... {item.percent}%</span> : item.stage === "uploaded" ? <span>✓ ההעלאה הושלמה · מתחיל ניתוח</span> : item.stage === "processing" ? <><span className="font-semibold text-indigo-600">✨ Gemini מנתח</span>{pages && <span>📄 {pages}</span>}{elapsed != null && <span>⏱️ עברו {formatSeconds(elapsed)}</span>}{eta != null && <span className="font-semibold text-amber-600">⏳ נותרו כ־{formatSeconds(eta)}</span>}</> : <span>{statusLabel[item.status || ""] || "הסתיים"}</span>}</div></div>{item.stage === "done" ? <CheckCircle2 className="text-emerald-600" size={20}/> : <Loader2 className="animate-spin text-indigo-600" size={20}/>}</div>{(item.stage === "processing" || item.stage === "uploaded") && <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-indigo-600 transition-all duration-500" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}/></div>}{item.stage === "processing" && <div className="mt-2 flex items-center gap-2 text-xs text-slate-400"><Clock3 size={14}/>{eta != null ? `הערכת זמן מתעדכנת בזמן אמת · כ־${formatSeconds(eta)} לסיום` : "מחשב הערכת זמן לפי קצב העיבוד..."}</div>}{item.error && <p className="mt-2 text-sm text-red-600">{item.error}</p>}</div>; })}</div></section>}

    {error && <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-medium text-red-700"><AlertTriangle size={18}/>{error}</div>}
    {analyses.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">מסמכים שהועלו ({analyses.length})</h2></div><div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3">{analyses.map((item) => <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`rounded-xl border p-3 text-right ${item.id === analysis?.id ? "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/30" : "border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"}`}><div className="truncate font-semibold">{item.filename}</div><div className="mt-1 text-xs text-slate-500">{statusLabel[item.status] || item.status}</div></button>)}</div></section>}
    {!analysis && <section className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-14 text-center dark:border-slate-700 dark:bg-slate-950"><FileSearch className="mx-auto mb-4 text-slate-400" size={44}/><h2 className="text-xl font-bold">אין מסמכים לניתוח</h2><p className="mt-2 text-sm text-slate-500">בחר מסמך אחד או כמה מסמכים כדי להתחיל.</p></section>}

    {analysis && <><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-wrap items-center gap-3"><div className="rounded-xl bg-indigo-50 p-3 text-indigo-600"><FileSearch size={22}/></div><div className="min-w-0 flex-1"><div className="truncate font-bold">{analysis.filename}</div><div className="text-sm text-slate-500">{analysis.document_type || "מסמך"} · {analysis.provider || "—"} {analysis.model ? `· ${analysis.model}` : ""}</div></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{statusLabel[analysis.status] || analysis.status}</span></div>{analysis.error_message && <p className="mt-3 whitespace-pre-wrap text-sm text-red-600">{analysis.error_message}</p>}</section>

    {analysis.status === "ANALYZED" && <>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">זוהו {data?.supplier_count ?? sections.length} ספקים</h2><p className="mt-1 text-xs text-slate-500">כל ספק הוא קבוצה עצמאית. שורות מסומנות לפי הקשר הספקי שנמצא במסמך.</p></div><span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">הפרדה אוטומטית</span></div><div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">{sections.map((section, index) => { const match = section.supplier_matching; return <div key={index} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><div className="font-bold">{supplierLabel(section)}</div><div className="mt-1 text-xs text-slate-500">מספר ספק: {section.supplier?.customer_number || "—"}</div><div className="mt-2 text-xs">{section.items?.length || 0} שורות · עמודים {(section.page_numbers || []).join(", ") || "—"}</div><div className={`mt-2 text-xs font-semibold ${match ? "text-emerald-600" : "text-amber-600"}`}>{match ? `התאמת ספק: ${Math.round((match.confidence || 0) * 100)}%` : "הספק לא נמצא בקטלוג — בדיקה נדרשת"}</div></div>})}</div></section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">בדיקה ואישור שורות</h2><p className="mt-1 text-xs text-slate-500">התאמות חד-משמעיות נבחרות אוטומטית לפי הספק שזוהה במסמך. רק שורות שאין להן התאמה בטוחה דורשות בחירה ידנית.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-sm"><thead className="bg-slate-50 text-right text-xs text-slate-500 dark:bg-slate-900"><tr><th className="p-3">ספק לפי המסמך</th><th className="p-3">פריט</th><th className="p-3">עמוד</th><th className="p-3">כמות</th><th className="p-3">מחיר</th><th className="p-3">התאמת מוצר</th><th className="p-3">מוצר במערכת</th><th className="p-3">ספק במערכת</th><th className="p-3">מחיר</th><th className="p-3">עדכון מחיר</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{items.map((item,index) => { const productMatch = item.product_matching?.best_match; const supplierMatch = item.supplier_matching; const section = sections[item.supplier_section_index ?? -1]; return <tr key={index}><td className="max-w-[170px] p-3"><div className="font-semibold">{supplierMatch?.supplier_name || item.supplier_context?.name || supplierLabel(section)}</div><div className="text-xs text-slate-400">{supplierMatch ? `${Math.round((supplierMatch.confidence || 0) * 100)}%` : "לא אומת"}</div></td><td className="max-w-[220px] p-3"><div className="font-medium">{item.description || "ללא תיאור"}</div><div className="text-xs text-slate-400">מק״ט: {item.supplier_sku || "—"} · ברקוד: {item.barcode || "—"}</div></td><td className="p-3">{item.page_number ?? "—"}</td><td className="p-3">{item.quantity ?? "—"} {item.unit || ""}</td><td className="p-3 font-bold">{item.unit_price && Number(item.unit_price) > 0 ? `${item.unit_price} ${data?.currency || "ILS"}` : "לא צוין"}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-xs font-bold ${productMatch?.decision === "AUTO_MATCH" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{productMatch ? `${productMatch.decision} · ${Math.round((productMatch.confidence || 0) * 100)}%` : "אין התאמה"}</span></td><td className="p-3"><SearchableSelect value={defaultProduct(item,index)} onChange={(value) => setMap(index,{product:value})} options={productOptions} placeholder="בחר מוצר..." /></td><td className="p-3"><SearchableSelect value={defaultSupplier(item,index)} onChange={(value) => setMap(index,{supplier:value})} options={supplierOptions} placeholder="בחר ספק..." /></td><td className="p-3"><label className="inline-flex items-center gap-2 text-xs"><input type="checkbox" checked={mappings[index]?.update ?? Boolean(productMatch && (productMatch.decision === "AUTO_MATCH" || ((productMatch.confidence || 0) >= 0.75 && productMatch.decision !== "LOW_CONFIDENCE")) && supplierMatch?.decision === "AUTO_MATCH" && Number(item.unit_price) > 0)} onChange={(e)=>setMap(index,{update:e.target.checked})}/><span>{productMatch?.decision === "AUTO_MATCH" && supplierMatch?.decision === "AUTO_MATCH" ? "אוטומטי" : "ידני"}</span></label></td></tr>; })}</tbody></table></div><div className="flex justify-end border-t border-slate-100 p-5 dark:border-slate-800"><button type="button" onClick={apply} disabled={busy} className="rounded-xl bg-emerald-600 px-5 py-3 font-bold text-white disabled:opacity-50">אישור ויישום</button></div></section>
    </>}
    </>}
  </div>;
}
