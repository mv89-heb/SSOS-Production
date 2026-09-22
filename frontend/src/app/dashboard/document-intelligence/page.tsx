"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, FileSearch, Loader2, Sparkles, Upload } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useProducts, useSuppliers } from "@/hooks/use-catalog";
import { documentIntelligenceService, type DocumentAnalysis, type ExtractedItem, type SupplierSection } from "@/services/document-intelligence-service";

const statusLabel: Record<string, string> = { UPLOADED: "הועלה", PROCESSING: "מנתח...", ANALYZED: "נותח — מוכן לבדיקה", PARTIALLY_APPLIED: "יושם חלקית — נותרו שורות לבדיקה", AI_UNAVAILABLE: "Gemini אינו מוגדר", FAILED: "הניתוח נכשל", APPLIED: "יושם בהצלחה" };
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
  const [analyses, setAnalyses] = useState<DocumentAnalysis[]>([]); const [selectedId, setSelectedId] = useState<number | null>(null); const [mappings, setMappings] = useState<Record<number, Mapping>>({}); const [selectedLines, setSelectedLines] = useState<Set<number>>(new Set()); const [newProductDrafts, setNewProductDrafts] = useState<Record<number, { open: boolean; name: string; supplier_id: number | string; supplier_sku: string; barcode: string; unit: string; units_per_carton: number | string; current_price: number | string }>>({}); const [progress, setProgress] = useState<UploadProgress[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (!busy) return; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [busy]);
  const analysis = analyses.find((item) => item.id === selectedId) ?? analyses[analyses.length - 1] ?? null;
  const data = analysis?.extracted_data;
  const productOptions = useMemo(() => [...products].sort((a, b) => a.name.localeCompare(b.name, "he")).map((p) => ({ id: p.id, name: p.name, extra: p.sku })), [products]);
  const supplierOptions = useMemo(() => [...suppliers].sort((a, b) => a.name.localeCompare(b.name, "he")).map((s) => ({ id: s.id, name: s.name, extra: s.customer_number })), [suppliers]);
  const items = useMemo<ExtractedItem[]>(() => Array.isArray(data?.items) ? data.items : [], [data]);
  const sections = useMemo<SupplierSection[]>(() => Array.isArray(data?.supplier_sections) ? data.supplier_sections : [], [data]);
  const appliedIndexes = useMemo(() => new Set<number>((Array.isArray(data?.applied_line_indexes) ? data.applied_line_indexes : []).map(Number)), [data]);  const selectableIndexes = useMemo(() => items.map((_, index) => index).filter((index) => !appliedIndexes.has(index)), [items, appliedIndexes]);
  const allSelected = selectableIndexes.length > 0 && selectableIndexes.every((index) => selectedLines.has(index));
  const toggleAllLines = () => setSelectedLines((current) => { const next = new Set(current); if (allSelected) selectableIndexes.forEach((index) => next.delete(index)); else selectableIndexes.forEach((index) => next.add(index)); return next; });
  const toggleLine = (index: number) => setSelectedLines((current) => { const next = new Set(current); if (next.has(index)) next.delete(index); else next.add(index); return next; });
  const productOptionsForItem = (item: ExtractedItem) => {
    const supplierId = item.supplier_matching?.supplier_id;
    const supplierProducts = supplierId ? products.filter((product) => product.supplier_id === supplierId) : products;
    const suggestions = (item.product_matching?.suggestions || []).map((suggestion) => ({ id: suggestion.product_id, name: suggestion.product_name, extra: `${Math.round((suggestion.confidence || 0) * 100)}%${suggestion.supplier_name ? ` · ${suggestion.supplier_name}` : ""}` }));
    const suggestionIds = new Set(suggestions.map((option) => option.id));
    const catalog = supplierProducts.filter((product) => !suggestionIds.has(product.id)).sort((a, b) => a.name.localeCompare(b.name, "he")).map((product) => ({ id: product.id, name: product.name, extra: product.sku }));
    return [...suggestions, ...catalog];
  };
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
      const productId = map.product || autoProduct;
      const supplierId = map.supplier || autoSupplier;
      const autoUpdatePrice = Boolean(productId && supplierId && Number.isFinite(numericPrice) && numericPrice > 0);
      return { line_index: index, product_id: productId, supplier_id: supplierId, price: Number.isFinite(numericPrice) && numericPrice > 0 ? numericPrice : undefined, currency: data?.currency || "ILS", unit: item.unit, package_quantity: item.package_quantity, update_price: map.update ?? autoUpdatePrice, match_method: product?.method || "MANUAL_REVIEW", match_confidence: product?.confidence };
    });
    const pending = lines.filter((line) => !appliedIndexes.has(line.line_index) && selectedLines.has(line.line_index));
    const ready = pending.filter((line) => line.product_id && line.supplier_id);
    if (!ready.length) { setError("אין כרגע שורות מסומנות שניתן ליישם. סמן שורות ובחר מוצר וספק לפי הצורך."); return; }
    const unresolvedCount = pending.length - ready.length;
    setBusy(true); setError("");
    try {
      const result = await documentIntelligenceService.apply(analysis.id, ready);
      setAnalyses((all) => all.map((item) => item.id === result.id ? result : item));
      setMappings((current) => ({ ...current }));
      setSelectedLines((current) => { const next = new Set(current); ready.forEach((line) => next.delete(line.line_index)); return next; });
      await queryClient.invalidateQueries({ queryKey: ["products"] });
      if (unresolvedCount > 0) setError(`יושמו ${ready.length} שורות. ${unresolvedCount} שורות נשארו לבדיקה — ניתן להשלים אותן אחר כך.`);
    } catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן ליישם את הנתונים"); }
    finally { setBusy(false); }
  }

  const openNewProduct = (item: ExtractedItem, index: number) => {
    const supplierId = item.supplier_matching?.supplier_id || "";
    setNewProductDrafts((current) => ({ ...current, [index]: { open: true, name: item.description || "", supplier_id: supplierId, supplier_sku: item.supplier_sku || "", barcode: item.barcode || "", unit: item.unit || "", units_per_carton: item.package_quantity ?? "", current_price: item.unit_price ?? "" } }));
  };
  const updateNewProduct = (index: number, patch: Partial<{ open: boolean; name: string; supplier_id: number | string; supplier_sku: string; barcode: string; unit: string; units_per_carton: number | string; current_price: number | string }>) => setNewProductDrafts((current) => ({ ...current, [index]: { ...(current[index] || { open: true, name: "", supplier_id: "", supplier_sku: "", barcode: "", unit: "", units_per_carton: "", current_price: "" }), ...patch } }));
  async function createProductFromLine(index: number) {
    if (!analysis) return;
    const draft = newProductDrafts[index];
    if (!draft) return;
    if (!draft.name.trim() || !draft.supplier_id) { setError("יש למלא שם מוצר וספק לפני ההוספה לקטלוג."); return; }
    setBusy(true); setError("");
    try {
      const result = await documentIntelligenceService.createProductFromLine(analysis.id, index, { name: draft.name.trim(), supplier_id: Number(draft.supplier_id), supplier_sku: draft.supplier_sku.trim() || undefined, barcode: draft.barcode.trim() || undefined, unit: draft.unit.trim() || undefined, units_per_carton: draft.units_per_carton === "" ? undefined : Number(draft.units_per_carton), current_price: draft.current_price === "" ? 0 : Number(draft.current_price), currency: data?.currency || "ILS" });
      setAnalyses((all) => all.map((item) => item.id === result.analysis.id ? result.analysis : item));
      setNewProductDrafts((current) => ({ ...current, [index]: { ...draft, open: false } }));
      setMappings((current) => ({ ...current, [index]: { ...current[index], product: result.product.id, supplier: result.product.supplier_id, update: true } }));
      await queryClient.invalidateQueries({ queryKey: ["products"] });
      setError(`המוצר "${result.product.name}" נוסף לקטלוג והשורה ${index + 1} יושמה.`);
    } catch (err: any) { setError(err?.friendlyMessage || err?.response?.data?.message || "לא ניתן להוסיף את המוצר לקטלוג"); }
    finally { setBusy(false); }
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

    {(analysis.status === "ANALYZED" || analysis.status === "PARTIALLY_APPLIED") && <>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">זוהו {data?.supplier_count ?? sections.length} ספקים</h2><p className="mt-1 text-xs text-slate-500">כל ספק הוא קבוצה עצמאית. שורות מסומנות לפי הקשר הספקי שנמצא במסמך.</p></div><span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">הפרדה אוטומטית</span></div><div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">{sections.map((section, index) => { const match = section.supplier_matching; return <div key={index} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><div className="font-bold">{supplierLabel(section)}</div><div className="mt-1 text-xs text-slate-500">מספר ספק: {section.supplier?.customer_number || "—"}</div><div className="mt-2 text-xs">{section.items?.length || 0} שורות · עמודים {(section.page_numbers || []).join(", ") || "—"}</div><div className={`mt-2 text-xs font-semibold ${match ? "text-emerald-600" : "text-amber-600"}`}>{match ? `התאמת ספק: ${Math.round((match.confidence || 0) * 100)}%` : "הספק לא נמצא בקטלוג — בדיקה נדרשת"}</div></div>})}</div></section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">בדיקה ואישור שורות</h2><p className="mt-1 text-xs text-slate-500">התאמות חד-משמעיות נבחרות אוטומטית לפי הספק שזוהה במסמך. רק שורות שאין להן התאמה בטוחה דורשות בחירה ידנית.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[1150px] text-sm"><thead className="bg-slate-50 text-right text-xs text-slate-500 dark:bg-slate-900"><tr><th className="p-3"><label className="inline-flex cursor-pointer items-center gap-2 whitespace-nowrap"><input type="checkbox" checked={allSelected} onChange={toggleAllLines} aria-label="סמן את כל השורות" /><span>סמן הכול</span></label></th>><th className="p-3">ספק לפי המסמך</th><th className="p-3">פריט</th><th className="p-3">עמוד</th><th className="p-3">כמות</th><th className="p-3">מחיר</th><th className="p-3">התאמת מוצר</th><th className="p-3">מוצר במערכת</th><th className="p-3">ספק במערכת</th><th className="p-3">מחיר</th><th className="p-3">עדכון מחיר</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{items.map((item,index) => { const productMatch = item.product_matching?.best_match; const supplierMatch = item.supplier_matching; const section = sections[item.supplier_section_index ?? -1]; const suggestion = item.product_matching?.suggestions?.[0]; const isApplied = appliedIndexes.has(index); const isStrong = Boolean(productMatch && ((productMatch.decision === "AUTO_MATCH") || ((productMatch.confidence || 0) >= 0.75 && productMatch.decision !== "LOW_CONFIDENCE"))); return <tr key={index} className={isApplied ? "bg-emerald-50/40 dark:bg-emerald-950/10" : ""}><td className="p-3"><input type="checkbox" checked={selectedLines.has(index)} disabled={isApplied} onChange={() => toggleLine(index)} aria-label={`סמן שורה ${index + 1}`} /></td><td className="max-w-[170px] p-3"><div className="font-semibold">{supplierMatch?.supplier_name || item.supplier_context?.name || supplierLabel(section)}</div><div className="text-xs text-slate-400">{supplierMatch ? `${Math.round((supplierMatch.confidence || 0) * 100)}%` : "לא אומת"}</div></td><td className="max-w-[220px] p-3"><div className="font-medium">{item.description || "ללא תיאור"}</div><div className="text-xs text-slate-400">מק״ט: {item.supplier_sku || "—"} · ברקוד: {item.barcode || "—"}</div></td><td className="p-3">{item.page_number ?? "—"}</td><td className="p-3">{item.quantity ?? "—"} {item.unit || ""}</td><td className="p-3 font-bold">{item.unit_price && Number(item.unit_price) > 0 ? `${item.unit_price} ${data?.currency || "ILS"}` : "לא צוין"}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-xs font-bold ${isStrong ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{isApplied ? "✓ יושם" : isStrong ? `אוטומטי · ${Math.round((productMatch?.confidence || 0) * 100)}%` : suggestion ? `נדרשת בדיקה · הצעה ${Math.round((suggestion.confidence || 0) * 100)}%` : "לא נמצאה התאמה בטוחה"}</span></td><td className="p-3">
  {isApplied ? <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">השורה יושמה בקטלוג</div> : <>
    <SearchableSelect value={defaultProduct(item,index)} onChange={(value) => setMap(index,{product:value})} options={productOptionsForItem(item)} placeholder={suggestion ? "בדוק/בחר מוצר..." : "בחר מוצר..."} />
    {!isStrong && <button type="button" onClick={() => openNewProduct(item,index)} className="mt-2 inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-300">＋ הוסף מוצר לקטלוג</button>}
    {newProductDrafts[index]?.open && <div className="mt-3 w-[360px] max-w-full rounded-xl border border-indigo-200 bg-indigo-50/70 p-3 dark:border-indigo-800 dark:bg-indigo-950/20">
      <div className="mb-2 font-bold text-indigo-800 dark:text-indigo-200">מוצר חדש בקטלוג</div>
      <div className="grid gap-2">
        <input value={newProductDrafts[index].name} onChange={(e)=>updateNewProduct(index,{name:e.target.value})} placeholder="שם מוצר" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        <SearchableSelect value={newProductDrafts[index].supplier_id} onChange={(value)=>updateNewProduct(index,{supplier_id:value})} options={supplierOptions} placeholder="בחר ספק..." />
        <div className="grid grid-cols-2 gap-2">
          <input value={newProductDrafts[index].supplier_sku} onChange={(e)=>updateNewProduct(index,{supplier_sku:e.target.value})} placeholder="מק״ט ספק" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
          <input value={newProductDrafts[index].barcode} onChange={(e)=>updateNewProduct(index,{barcode:e.target.value})} placeholder="ברקוד" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <input value={newProductDrafts[index].unit} onChange={(e)=>updateNewProduct(index,{unit:e.target.value})} placeholder="יחידה" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
          <input type="number" min="1" step="1" value={newProductDrafts[index].units_per_carton} onChange={(e)=>updateNewProduct(index,{units_per_carton:e.target.value})} placeholder="יח׳ בקרטון" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
          <input type="number" min="0" step="0.01" value={newProductDrafts[index].current_price} onChange={(e)=>updateNewProduct(index,{current_price:e.target.value})} placeholder="מחיר" className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={()=>createProductFromLine(index)} disabled={busy} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">הוסף לקטלוג ויישם</button>
          <button type="button" onClick={()=>updateNewProduct(index,{open:false})} disabled={busy} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold dark:border-slate-700 dark:bg-slate-900">ביטול</button>
        </div>
      </div>
    </div>}
  </>}
</td><td className="p-3"><SearchableSelect value={defaultSupplier(item,index)} onChange={(value) => setMap(index,{supplier:value})} options={supplierOptions} placeholder="בחר ספק..." /></td><td className="p-3"><label className="inline-flex items-center gap-2 text-xs"><input type="checkbox" checked={mappings[index]?.update ?? Boolean(productMatch && (productMatch.decision === "AUTO_MATCH" || ((productMatch.confidence || 0) >= 0.75 && productMatch.decision !== "LOW_CONFIDENCE")) && supplierMatch?.decision === "AUTO_MATCH" && Number(item.unit_price) > 0)} onChange={(e)=>setMap(index,{update:e.target.checked})}/><span>{productMatch?.decision === "AUTO_MATCH" && supplierMatch?.decision === "AUTO_MATCH" ? "אוטומטי" : "ידני"}</span></label></td></tr>; })}</tbody></table></div><div className="flex justify-end border-t border-slate-100 p-5 dark:border-slate-800"><button type="button" onClick={apply} disabled={busy} className="rounded-xl bg-emerald-600 px-5 py-3 font-bold text-white disabled:opacity-50">{selectedLines.size ? `אישור ויישום ${selectedLines.size} שורות מסומנות` : "סמן שורות ליישום"}</button></div></section>
    </>}
    </>}
  </div>;
}
