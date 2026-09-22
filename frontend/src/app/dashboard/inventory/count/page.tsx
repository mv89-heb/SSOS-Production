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
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("remaining");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannerError, setScannerError] = useState<string | null>(null);
  const [draftRestored, setDraftRestored] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const scanTimer = useRef<number | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["inventory", "summary"],
    queryFn: inventoryService.getSummary,
    staleTime: 10_000,
  });
  const products = data?.products ?? [];

  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.quantities && typeof draft.quantities === "object") setQuantities(draft.quantities);
        if (typeof draft.note === "string") setNote(draft.note);
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
    try {
      if (hasDraft) localStorage.setItem(DRAFT_KEY, JSON.stringify({ quantities, note, savedAt: new Date().toISOString() }));
      else localStorage.removeItem(DRAFT_KEY);
    } catch {
      // Local storage may be unavailable; counting still works.
    }
  }, [quantities, note, draftRestored]);

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
      const result = await apiClient.post<{ success: boolean; counted: number }>(
        "/api/inventory/count/bulk",
        { items, note: note.trim() || undefined }
      );
      setMessage("נשמרה ספירה עבור " + result.data.counted + " מוצרים והמלאי עודכן.");
      setQuantities({});
      setNote("");
      localStorage.removeItem(DRAFT_KEY);
      setFilter("remaining");
      await qc.invalidateQueries({ queryKey: ["inventory"] });
      await refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "שמירת הספירה נכשלה.");
    } finally {
      setSaving(false);
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

      {message && (
        <div className="flex items-start gap-2 rounded-2xl bg-emerald-50 p-4 text-sm font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
          <CheckCircle2 className="mt-0.5 shrink-0" size={18}/><span>{message}</span>
        </div>
      )}

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
        {counted && <div className={`shrink-0 text-left text-sm font-black ${delta === 0 ? "text-slate-500" : delta > 0 ? "text-emerald-600" : "text-red-600"}`}>{delta > 0 ? "+" : ""}{fmt(delta ?? 0)}</div>}
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
