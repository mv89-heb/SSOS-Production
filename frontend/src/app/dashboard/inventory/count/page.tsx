"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Camera, Check, CheckCircle2, ChevronDown, ChevronUp, ClipboardCheck,
  Hash, Loader2, Minus, Package, Plus, RotateCcw, Search, Trash2, Warehouse, X
} from "lucide-react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/services/api-client";
import { inventoryService } from "@/services/inventory-service";
import type { Product } from "@/types";

type Filter = "all" | "remaining" | "counted" | "difference";
const DRAFT_KEY = "ssos_inventory_count_draft_v2";

const fmt = (value: number) =>
  new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 }).format(value);

const productUnit = (product: Product) => product.stock_unit || product.unit || "יחידה";

export default function InventoryCountPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [note, setNote] = useState("");
  const [countId, setCountId] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("remaining");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannerError, setScannerError] = useState<string | null>(null);
  const [draftRestored, setDraftRestored] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [showLatestReport, setShowLatestReport] = useState(true);
  const [creatingOrderFor, setCreatingOrderFor] = useState<number | null>(null);
  const [orderMessage, setOrderMessage] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const scanTimer = useRef<number | null>(null);

  const latestCount = useQuery({
    queryKey: ["inventory", "latest-count"],
    queryFn: inventoryService.getLatestCount,
    staleTime: 10_000,
  });

  const countHistory = useQuery({
    queryKey: ["inventory", "count-history", 30],
    queryFn: () => inventoryService.getCountHistory(30),
    staleTime: 10_000,
  });
  const [expandedHistoryDate, setExpandedHistoryDate] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["inventory", "summary"],
    queryFn: inventoryService.getSummary,
    staleTime: 10_000,
  });
  const recommendations = useQuery({
    queryKey: ["inventory", "recommendations", 30],
    queryFn: () => inventoryService.getRecommendations({ lookback_days: 30, safety_days: 2, limit: 500 }),
    staleTime: 60_000,
  });
  const currentUser = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await apiClient.get<{ user: { role: string } }>("/api/auth/me")).data.user,
    retry: false,
    staleTime: 60_000,
  });
  const countStatus = useQuery({
    queryKey: ["inventory", "count-status"],
    queryFn: async () => (await apiClient.get<{ due: boolean; due_product_ids: number[]; assigned_products: number; completion_percent: number; priority_products: number; rotation_cycle_weeks: number }>("/api/inventory/planning/count-status")).data,
    staleTime: 15_000,
  });
  const allProducts = data?.products ?? [];
  const assignedIds = useMemo(() => new Set(countStatus.data?.due_product_ids ?? []), [countStatus.data?.due_product_ids]);
  const products = currentUser.data?.role === "employee"
    ? allProducts.filter((product) => assignedIds.has(product.id))
    : allProducts;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.quantities && typeof draft.quantities === "object") setQuantities(draft.quantities);
        if (typeof draft.note === "string") setNote(draft.note);
        if (typeof draft.countId === "string") setCountId(draft.countId);
      }
    } catch {
      // Ignore malformed local drafts.
    } finally {
      setDraftRestored(true);
    }
  }, []);

  useEffect(() => {
    if (!draftRestored) return;
    const hasDraft = Object.keys(quantities).length > 0 || note.trim().length > 0;
    if (!hasDraft && countId) {
      setCountId("");
      try { localStorage.removeItem(DRAFT_KEY); } catch { /* local storage may be unavailable */ }
      return;
    }
    if (hasDraft && !countId) {
      setCountId(crypto.randomUUID());
      return;
    }
    try {
      if (hasDraft) localStorage.setItem(DRAFT_KEY, JSON.stringify({ quantities, note, countId, savedAt: new Date().toISOString() }));
      else localStorage.removeItem(DRAFT_KEY);
    } catch {
      // Local storage may be unavailable; counting still works.
    }
  }, [quantities, note, countId, draftRestored]);

  useEffect(() => () => {
    if (scanTimer.current) window.clearTimeout(scanTimer.current);
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((track) => track.stop());
  }, []);

  const countedIds = useMemo(() => new Set(
    Object.entries(quantities)
      .filter(([, value]) => value !== "")
      .map(([id]) => Number(id))
  ), [quantities]);

  const rows = useMemo(() => {
    const q = search.trim().toLocaleLowerCase("he");
    return products.filter((p) => {
      const matchesSearch = !q || [p.name, p.sku, p.barcode, p.category, p.supplier_sku]
        .filter(Boolean)
        .some((v) => String(v).toLocaleLowerCase("he").includes(q));
      if (!matchesSearch) return false;
      const raw = quantities[p.id];
      const counted = raw !== undefined && raw !== "";
      const difference = counted && Number(raw) !== Number(p.current_stock ?? 0);
      if (filter === "remaining") return !counted;
      if (filter === "counted") return counted;
      if (filter === "difference") return difference;
      return true;
    });
  }, [products, search, quantities, filter]);

  const allCounted = products.filter((p) => quantities[p.id] !== undefined && quantities[p.id] !== "").length;
  const differenceCount = products.filter((p) => {
    const raw = quantities[p.id];
    return raw !== undefined && raw !== "" && Number(raw) !== Number(p.current_stock ?? 0);
  }).length;
  const remainingCount = products.length - allCounted;

  const setQuantity = (product: Product, value: string) => {
    if (!/^\d*$/.test(value)) return;
    setQuantities((current) => ({ ...current, [product.id]: value }));
    setExpanded(product.id);
  };

  const adjust = (product: Product, amount: number) => {
    const current = quantities[product.id] === undefined || quantities[product.id] === ""
      ? Number(product.current_stock ?? 0)
      : Number(quantities[product.id]);
    setQuantity(product, String(Math.max(0, current + amount)));
  };

  const markCounted = (product: Product) => {
    if (quantities[product.id] === undefined || quantities[product.id] === "") {
      setQuantity(product, String(product.current_stock ?? 0));
    }
  };

  const clearProduct = (product: Product) => {
    setQuantities((current) => {
      const next = { ...current };
      delete next[product.id];
      return next;
    });
  };

  const save = async () => {
    const filled = products.filter((p) => quantities[p.id] !== undefined && quantities[p.id] !== "");
    if (!filled.length || saving) return;
    setSaving(true);
    setMessage(null);
    try {
      const items = filled.map((p) => ({ product_id: p.id, quantity: Number(quantities[p.id]) }));
      if (items.some((item) => !Number.isInteger(item.quantity) || item.quantity < 0)) {
        throw new Error("יש להזין כמויות שלמות שאינן שליליות.");
      }
      const result = await apiClient.post<{ success: boolean; count_id: string; counted: number; counted_at: string; movements: any[] }>(
        "/api/inventory/count/bulk",
        { items, note: note.trim() || undefined, count_id: countId || crypto.randomUUID() }
      );
      setMessage("נשמרה ספירה עבור " + result.data.counted + " מוצרים והמלאי עודכן.");
      setQuantities({});
      setNote("");
      setCountId("");
      localStorage.removeItem(DRAFT_KEY);
      setFilter("remaining");
      await qc.invalidateQueries({ queryKey: ["inventory"] });
      await qc.invalidateQueries({ queryKey: ["inventory", "latest-count"] });
      await latestCount.refetch();
      await refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "שמירת הספירה נכשלה.");
    } finally {
      setSaving(false);
    }
  };

  const createSuggestedOrder = async (supplierId: number) => {
    if (creatingOrderFor !== null) return;
    const supplierItems = (recommendations.data ?? [])
      .filter((row) => row.status === "urgent" || row.status === "reorder")
      .filter((row) => {
        const product = products.find((item) => item.id === row.product_id);
        return Number(product?.supplier_id ?? row.supplier_schedule?.supplier_id) === supplierId
          && Number(row.recommended_order) > 0
          && Number(product?.current_price ?? 0) > 0;
      })
      .map((row) => ({ product_id: row.product_id, quantity: Math.ceil(Number(row.recommended_order)) }))
      .filter((item) => item.quantity > 0);
    if (!supplierItems.length) {
      setOrderMessage("אין מוצרים מתאימים להזמנה מספק זה. בדוק שיוך ספק ומחיר תקין לכל מוצר.");
      return;
    }
    setCreatingOrderFor(supplierId);
    setOrderMessage(null);
    try {
      const result = await apiClient.post<{ success: boolean; order: { id: number; order_number: string } }>(
        "/api/orders",
        { supplier_id: supplierId, items: supplierItems, notes: "טיוטת הזמנה שנוצרה מהמלצת ספירת מלאי לפי צריכה משוערת ב-30 הימים האחרונים." }
      );
      setOrderMessage(`נוצרה טיוטת הזמנה ${result.data.order.order_number} עם ${supplierItems.length} מוצרים. אפשר להמשיך למסך הזמנות רכש לבדיקה ואישור.`);
      router.push("/dashboard/orders");
    } catch (error) {
      setOrderMessage(error instanceof Error ? error.message : "יצירת טיוטת ההזמנה נכשלה.");
    } finally {
      setCreatingOrderFor(null);
    }
  };

  const resetDraft = () => {
    setQuantities({});
    setNote("");
    setMessage(null);
    localStorage.removeItem(DRAFT_KEY);
    setShowReset(false);
  };

  const openScanner = async () => {
    setScannerError(null);
    setScannerOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      if (videoRef.current) videoRef.current.srcObject = stream;
      const BarcodeDetectorCtor = (window as any).BarcodeDetector;
      if (!BarcodeDetectorCtor) {
        setScannerError("הדפדפן לא תומך בסריקת ברקוד מובנית. אפשר להשתמש בחיפוש לפי מק״ט או ברקוד.");
        return;
      }
      const detector = new BarcodeDetectorCtor({
        formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "itf", "qr_code"],
      });
      const scan = async () => {
        if (!videoRef.current || videoRef.current.readyState < 2) {
          scanTimer.current = window.setTimeout(scan, 250);
          return;
        }
        try {
          const codes = await detector.detect(videoRef.current);
          const value = codes?.[0]?.rawValue;
          if (value) {
            const product = products.find((p) => String(p.barcode || "") === value || String(p.sku || "") === value || String(p.supplier_sku || "") === value);
            if (product) {
              setSearch("");
              setFilter("all");
              setExpanded(product.id);
              window.setTimeout(() => document.getElementById(`product-${product.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
              closeScanner();
              return;
            }
            setScannerError(`נמצא ברקוד ${value}, אך הוא לא קיים בקטלוג.`);
          }
        } catch {
          // Continue scanning frames.
        }
        scanTimer.current = window.setTimeout(scan, 350);
      };
      scan();
    } catch {
      setScannerError("אין גישה למצלמה. יש לאשר הרשאת מצלמה בדפדפן.");
    }
  };

  const closeScanner = () => {
    if (scanTimer.current) window.clearTimeout(scanTimer.current);
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((track) => track.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
    setScannerOpen(false);
  };

  return (
    <div dir="rtl" className="min-h-screen space-y-4 pb-28">
      <header className="rounded-3xl bg-gradient-to-br from-indigo-700 via-blue-600 to-cyan-600 p-5 text-white shadow-lg sm:p-7">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-blue-100"><Warehouse size={17}/> מחסן ומלאי</div>
            <h1 className="mt-1 text-2xl font-black sm:text-3xl">ספירת מלאי</h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-blue-100">סופרים מוצר-מוצר. כל שינוי נשמר כטיוטה בטלפון עד לשמירה במערכת.</p>
          </div>
          <button onClick={() => router.push("/dashboard/inventory")} className="hidden min-h-11 rounded-xl bg-white/10 px-4 text-sm font-black ring-1 ring-white/20 sm:block">חזרה</button>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2">
          <MiniStat label="סה״כ" value={products.length} />
          <MiniStat label="נספרו" value={allCounted} />
          <MiniStat label="נשארו" value={remainingCount} />
        </div>
      </header>

      {currentUser.data?.role === "employee" && countStatus.data && (
        <section className="rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-indigo-950 dark:border-indigo-900 dark:bg-indigo-950/30 dark:text-indigo-100">
          <div className="flex items-start gap-3">
            <ClipboardCheck className="mt-1 shrink-0" size={22} />
            <div>
              <h2 className="font-black">המשימה השבועית שלך — ספירה מחזורית</h2>
              <p className="mt-1 text-sm leading-6">אין צורך לספור את כל הקטלוג. השבוע הוקצו לך {countStatus.data.assigned_products} מוצרים מתוך {data?.products.length ?? 0}; מוצרים שאזלו או מתחת למינימום מקבלים עדיפות. הקטלוג הרגיל מסתובב במחזור של {countStatus.data.rotation_cycle_weeks} שבועות.</p>
              <p className="mt-1 text-sm font-bold">התקדמות השבוע: {countStatus.data.completion_percent}% · נותרו {products.length} מוצרים לספירה.</p>
            </div>
          </div>
        </section>
      )}

      {message && (
        <div className="flex items-start gap-2 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
          <CheckCircle2 className="mt-0.5 shrink-0" size={18}/><span>{message}</span>
        </div>
      )}
      {latestCount.data?.has_count && (
        <section className="overflow-hidden rounded-3xl border border-indigo-200 bg-white shadow-sm dark:border-indigo-900/60 dark:bg-slate-950">
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"><ClipboardCheck size={21}/></div>
              <div>
                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-300">הספירה האחרונה שנשמרה</div>
                <div className="mt-1 text-lg font-black">{latestCount.data.counted} מוצרים</div>
                <div className="mt-1 text-xs text-slate-500">{latestCount.data.counted_at ? new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(new Date(latestCount.data.counted_at)) : ""}</div>
              </div>
            </div>
            <button onClick={() => setShowLatestReport((current) => !current)} className="min-h-11 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white">{showLatestReport ? "הסתר פירוט ספירה" : "הצג פירוט ספירה"}</button>
          </div>
          {showLatestReport && (
            <div className="border-t border-indigo-100 p-4 dark:border-indigo-950">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-black">דוח ספירת המלאי האחרונה — כל המוצרים שנספרו</h3>
                <span className="text-xs text-slate-500">תאריך הספירה: {latestCount.data.counted_at ? new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(new Date(latestCount.data.counted_at)) : "—"}</span>
              </div>
              <div className="w-full max-w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="w-full min-w-[620px] text-right text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                    <tr><th className="px-3 py-3">מוצר</th><th className="px-3 py-3">מק״ט</th><th className="px-3 py-3">כמות שנספרה</th><th className="px-3 py-3">יחידת מלאי</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {latestCount.data.movements.map((movement) => {
                      const product = products.find((item) => item.id === movement.product_id);
                      return <tr key={movement.id}>
                        <td className="px-3 py-3 font-bold">{product?.name || `מוצר #${movement.product_id}`}</td>
                        <td className="px-3 py-3 text-slate-500">{product?.sku || "—"}</td>
                        <td className="px-3 py-3 font-black">{fmt(movement.quantity)}</td>
                        <td className="px-3 py-3 text-slate-500">{product ? productUnit(product) : "—"}</td>
                      </tr>;
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}


      <section id="count-history" className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-2 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
          <div>
            <h2 className="text-lg font-black">היסטוריית ספירות — 30 הימים האחרונים</h2>
            <p className="mt-1 text-sm text-slate-500">כל הרשומות שנשמרו מוצגות לפי יום, כולל ספירות ישנות שנשמרו מוצר-מוצר.</p>
          </div>
          <button onClick={() => countHistory.refetch()} className="min-h-10 rounded-xl bg-slate-100 px-4 text-sm font-bold dark:bg-slate-900">רענן היסטוריה</button>
        </div>
        {countHistory.isLoading ? (
          <div className="p-5 text-sm text-slate-500">טוען ספירות שמורות…</div>
        ) : countHistory.isError ? (
          <div className="p-5 text-sm text-red-600">לא ניתן לטעון את היסטוריית הספירות כרגע.</div>
        ) : !countHistory.data?.length ? (
          <div className="p-5 text-sm text-slate-500">לא נמצאו ספירות בטווח הזה.</div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {countHistory.data.map((entry: any, index: number) => {
              const dateKey = entry.count_id || entry.counted_at || String(index);
              const expanded = expandedHistoryDate === dateKey;
              return <div key={dateKey}>
                <button onClick={() => setExpandedHistoryDate(expanded ? null : dateKey)} className="flex w-full items-center justify-between gap-3 p-4 text-right hover:bg-slate-50 dark:hover:bg-slate-900/60">
                  <div>
                    <div className="font-black">{entry.counted_at ? new Intl.DateTimeFormat("he-IL", { dateStyle: "full" }).format(new Date(entry.counted_at)) : "תאריך לא ידוע"}</div>
                    <div className="mt-1 text-xs text-slate-500">{entry.counted_at ? new Intl.DateTimeFormat("he-IL", { timeStyle: "short" }).format(new Date(entry.counted_at)) : ""} · {entry.counted} רשומות מוצר</div>
                  </div>
                  <div className="flex items-center gap-2 text-sm font-bold text-indigo-600">{expanded ? "הסתר פרטים" : "הצג פרטים"} {expanded ? <ChevronUp size={17}/> : <ChevronDown size={17}/>}</div>
                </button>
                {expanded && (
                  <div className="px-3 pb-4 sm:px-4">
                    <div className="w-full max-w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                      <table className="w-full min-w-[580px] text-right text-sm">
                        <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-3 py-3">מוצר</th><th className="px-3 py-3">מק״ט</th><th className="px-3 py-3">כמות שנספרה</th><th className="px-3 py-3">יחידה</th></tr></thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                          {(entry.movements || []).map((movement: any) => {
                            const product = products.find((item) => item.id === movement.product_id);
                            return <tr key={movement.id}>
                              <td className="px-3 py-3 font-bold">{product?.name || `מוצר #${movement.product_id}`}</td>
                              <td className="px-3 py-3 text-slate-500">{product?.sku || "—"}</td>
                              <td className="px-3 py-3 font-black">{fmt(Number(movement.quantity))}</td>
                              <td className="px-3 py-3 text-slate-500">{product ? productUnit(product) : "—"}</td>
                            </tr>;
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>;
            })}
          </div>
        )}
      </section>


      <section className="overflow-hidden rounded-3xl border border-emerald-200 bg-white shadow-sm dark:border-emerald-900/60 dark:bg-slate-950">
        <div className="border-b border-emerald-100 p-5 dark:border-emerald-950">
          <h2 className="text-lg font-black">יצירת טיוטות הזמנה לפי ספק</h2>
          <p className="mt-1 text-sm text-slate-500">פירוט הצריכה השבועית, ימי הכיסוי והמלצת הכמות מוצג במסך ניהול מלאי. כאן נשארה רק הפעולה הייחודית: יצירת טיוטת הזמנה לפי ספק, כדי לא להציג את אותה טבלת המלצות פעמיים.</p>
          <a href="/dashboard/inventory" className="mt-3 inline-flex min-h-10 items-center rounded-xl border border-emerald-200 px-3 py-2 text-sm font-bold text-emerald-800 hover:bg-emerald-50 dark:border-emerald-900 dark:text-emerald-300 dark:hover:bg-emerald-950/30">לצפייה בהמלצות המלאי לפי מוצר ←</a>
        </div>
        {recommendations.isLoading ? <div className="p-5 text-sm text-slate-500">בודק אילו ספקים מתאימים ליצירת טיוטה…</div> :
          recommendations.isError ? <div className="p-5 text-sm text-red-600">לא ניתן לטעון את המלצות ההזמנה. אפשר לעבור למסך ניהול מלאי ולנסות שוב.</div> :
          <div className="space-y-3 p-4">
            {orderMessage && <div className="rounded-xl bg-indigo-50 p-3 text-sm font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">{orderMessage}</div>}
            <div className="flex flex-wrap gap-2">
              {[...new Set((recommendations.data ?? []).filter((row) => row.data_ready && (row.status === "urgent" || row.status === "reorder") && Number(row.recommended_order) > 0).map((row) => Number(products.find((p) => p.id === row.product_id)?.supplier_id ?? row.supplier_schedule?.supplier_id)).filter((id) => Number.isInteger(id) && id > 0))].map((supplierId) => {
                const count = (recommendations.data ?? []).filter((row) => Number(products.find((p) => p.id === row.product_id)?.supplier_id ?? row.supplier_schedule?.supplier_id) === supplierId && row.data_ready && (row.status === "urgent" || row.status === "reorder") && Number(row.recommended_order) > 0 && Number(products.find((p) => p.id === row.product_id)?.current_price ?? 0) > 0).length;
                return <button key={supplierId} disabled={creatingOrderFor !== null} onClick={() => createSuggestedOrder(supplierId)} className="min-h-11 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-black text-white disabled:opacity-50">{creatingOrderFor === supplierId ? "יוצר טיוטה…" : `צור טיוטת הזמנה · ספק #${supplierId} · ${count} מוצרים`}</button>;
              })}
              {[...new Set((recommendations.data ?? []).filter((row) => row.data_ready && (row.status === "urgent" || row.status === "reorder") && Number(row.recommended_order) > 0).map((row) => Number(products.find((p) => p.id === row.product_id)?.supplier_id ?? row.supplier_schedule?.supplier_id)).filter((id) => Number.isInteger(id) && id > 0))].length === 0 && <p className="text-sm text-slate-500">אין כרגע ספקים עם מוצרים שעומדים בתנאים ליצירת טיוטה.</p>}
            </div>
            <p className="text-xs leading-5 text-slate-500">הטיוטה אינה נשלחת לספק ואינה מאושרת אוטומטית. מוצרים ללא נתוני צריכה מספקים, ספק תקין או מחיר תקין לא ייכללו.</p>
          </div>}
      </section>

      <section className="sticky top-1 z-30 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
        <div className="flex gap-2">
          <label className="relative min-w-0 flex-1">
            <Search className="absolute right-3 top-3.5 text-slate-400" size={18}/>
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש מוצר / מק״ט / ברקוד" className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 pr-10 pl-3 text-base font-bold outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"/>
          </label>
          <button onClick={openScanner} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm" aria-label="סריקת ברקוד"><Camera size={21}/></button>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          <FilterButton active={filter === "remaining"} onClick={() => setFilter("remaining")} label={`נשארו ${remainingCount}`} />
          <FilterButton active={filter === "counted"} onClick={() => setFilter("counted")} label={`נספרו ${allCounted}`} />
          <FilterButton active={filter === "difference"} onClick={() => setFilter("difference")} label={`הפרשים ${differenceCount}`} />
          <FilterButton active={filter === "all"} onClick={() => setFilter("all")} label="הכול" />
        </div>
      </section>

      {draftRestored && Object.keys(quantities).length > 0 && (
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs font-bold text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
          <span>טיוטת הספירה נשמרה במכשיר ומוכנה להמשך.</span>
          <button onClick={() => setShowReset(true)} className="shrink-0 rounded-lg px-2 py-1 underline">נקה טיוטה</button>
        </div>
      )}

      {isError && <div className="rounded-2xl bg-red-50 p-4 text-sm font-bold text-red-700">לא ניתן לטעון את המלאי. נסה לרענן.</div>}

      <section className="space-y-2">
        {isLoading ? (
          <div className="rounded-3xl bg-white p-10 text-center text-sm text-slate-500 shadow-sm dark:bg-slate-950">טוען מוצרים...</div>
        ) : rows.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-950">
            <Package className="mx-auto text-slate-300" size={40}/>
            <div className="mt-3 font-black">אין מוצרים להצגה</div>
            <p className="mt-1 text-sm text-slate-500">{filter === "remaining" ? "כל המוצרים כבר נספרו." : "נסה לשנות חיפוש או סינון."}</p>
          </div>
        ) : (
          rows.map((product) => <CountCard
            key={product.id}
            product={product}
            value={quantities[product.id] ?? ""}
            expanded={expanded === product.id}
            onExpand={() => setExpanded(expanded === product.id ? null : product.id)}
            onChange={(value) => setQuantity(product, value)}
            onAdjust={(amount) => adjust(product, amount)}
            onMark={() => markCounted(product)}
            onClear={() => clearProduct(product)}
          />)
        )}
      </section>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 p-3 shadow-2xl backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          <div className="min-w-0 flex-1">
            <div className="text-xs font-bold text-slate-500">מוכן לשמירה</div>
            <div className="truncate text-sm font-black">{allCounted} מתוך {products.length} מוצרים · {differenceCount} הפרשים</div>
          </div>
          <button onClick={() => setShowReset(true)} disabled={!allCounted} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 disabled:opacity-30 dark:border-slate-700" aria-label="נקה ספירה"><Trash2 size={19}/></button>
          <button onClick={save} disabled={!allCounted || saving} className="flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 font-black text-white shadow-lg disabled:opacity-40">
            {saving ? <Loader2 className="animate-spin" size={18}/> : <ClipboardCheck size={18}/>}
            שמור {allCounted}
          </button>
        </div>
      </div>

      {scannerOpen && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/80 sm:items-center sm:p-6">
          <div className="relative w-full max-w-lg overflow-hidden rounded-t-3xl bg-slate-950 text-white sm:rounded-3xl">
            <div className="flex items-center justify-between p-4">
              <div className="font-black">סריקת ברקוד</div>
              <button onClick={closeScanner} className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10"><X size={20}/></button>
            </div>
            <div className="relative aspect-[4/3] overflow-hidden bg-black">
              <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover"/>
              <div className="pointer-events-none absolute inset-x-10 top-1/2 h-24 -translate-y-1/2 rounded-2xl border-2 border-white/80"/>
            </div>
            <div className="p-4 text-center">
              {scannerError ? <div className="rounded-xl bg-red-950/60 p-3 text-sm font-bold text-red-200">{scannerError}</div> : <p className="text-sm text-slate-300">כוון את המצלמה לברקוד של המוצר.</p>}
            </div>
          </div>
        </div>
      )}

      {showReset && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl dark:bg-slate-900">
            <AlertTriangle className="text-amber-500" size={28}/>
            <h2 className="mt-3 text-lg font-black">לנקות את הספירה?</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">כל הכמויות שטרם נשמרו יימחקו מהמכשיר.</p>
            <div className="mt-5 flex gap-2">
              <button onClick={() => setShowReset(false)} className="flex-1 rounded-xl border border-slate-200 py-3 font-bold dark:border-slate-700">ביטול</button>
              <button onClick={resetDraft} className="flex-1 rounded-xl bg-red-600 py-3 font-black text-white">נקה</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CountCard({
  product, value, expanded, onExpand, onChange, onAdjust, onMark, onClear,
}: {
  product: Product; value: string; expanded: boolean;
  onExpand: () => void; onChange: (value: string) => void; onAdjust: (amount: number) => void;
  onMark: () => void; onClear: () => void;
}) {
  const counted = value !== "";
  const current = Number(product.current_stock ?? 0);
  const countedValue = counted ? Number(value) : null;
  const delta = countedValue === null ? null : countedValue - current;
  const unit = productUnit(product);
  return (
    <article id={`product-${product.id}`} className={`overflow-hidden rounded-2xl border shadow-sm transition ${counted ? "border-indigo-200 bg-indigo-50/40 dark:border-indigo-900/60 dark:bg-indigo-950/20" : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"}`}>
      <button onClick={onExpand} className="flex w-full items-center gap-3 p-4 text-right">
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${counted ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500 dark:bg-slate-800"}`}>
          {counted ? <Check size={21}/> : <Package size={21}/>}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-black">{product.name}</div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
            {product.sku && <span>מק״ט {product.sku}</span>}
            <span>במערכת: <b>{fmt(current)}</b> {unit}</span>
          </div>
        </div>
        {counted && <div className={`shrink-0 text-left text-sm font-black ${(delta ?? 0) === 0 ? "text-slate-500" : (delta ?? 0) > 0 ? "text-emerald-600" : "text-red-600"}`}>{(delta ?? 0) > 0 ? "+" : ""}{fmt(delta ?? 0)}</div>}
        {expanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
      </button>

      {expanded && (
        <div className="border-t border-slate-200 p-4 dark:border-slate-800">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <button onClick={() => onAdjust(-1)} className="flex h-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl font-black active:scale-95 dark:bg-slate-800" aria-label="הפחת אחת"><Minus/></button>
            <div className="w-28 text-center">
              <label className="text-xs font-bold text-slate-500">כמות שנספרה</label>
              <input autoFocus inputMode="numeric" type="number" min="0" step="1" value={value} onChange={(e) => onChange(e.target.value)} placeholder={String(current)} className="mt-1 h-16 w-full rounded-2xl border-2 border-indigo-200 bg-white text-center text-3xl font-black outline-none focus:border-indigo-600 dark:border-indigo-900 dark:bg-slate-900"/>
              <div className="mt-1 text-[11px] text-slate-400">{unit}</div>
            </div>
            <button onClick={() => onAdjust(1)} className="flex h-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl font-black active:scale-95 dark:bg-slate-800" aria-label="הוסף אחת"><Plus/></button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button onClick={onMark} className="flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-3 font-black text-white"><Check size={17}/> סמן כנספר</button>
            {counted ? <button onClick={onClear} className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 font-bold dark:border-slate-700"><RotateCcw size={17}/> בטל ספירה</button> : <div className="rounded-xl bg-slate-50 p-3 text-center text-xs font-bold text-slate-500 dark:bg-slate-900">הקלד כמות או השתמש ב־+ / −</div>}
          </div>
          {delta !== null && delta !== 0 && <div className={`mt-3 rounded-xl p-3 text-sm font-black ${delta > 0 ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300" : "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300"}`}>הפרש: {delta > 0 ? "+" : ""}{fmt(delta)} {unit}</div>}
        </div>
      )}
    </article>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-2xl bg-white/10 p-3 text-center ring-1 ring-white/10"><div className="text-[11px] font-bold text-blue-100">{label}</div><div className="mt-0.5 text-xl font-black">{fmt(value)}</div></div>;
}

function FilterButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return <button onClick={onClick} className={`shrink-0 rounded-full px-4 py-2 text-xs font-black transition ${active ? "bg-indigo-600 text-white shadow" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{label}</button>;
}
