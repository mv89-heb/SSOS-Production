"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, CircleHelp, Loader2, Plus, RefreshCw, Search, X } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { catalogService } from "@/services/catalog-service";
import type { MasterMatchSuggestion, SupplierProductListing } from "@/services/catalog-service";
import { ProductSortToggle } from "@/components/catalog/product-sort-toggle";
import { sortByHebrewName, type ProductSortDirection } from "@/lib/product-sorting";

const money = (value?: number | null, currency = "ILS") => {
  if (value == null) return "מחיר חסר";
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value); }
  catch { return `${value.toFixed(2)} ${currency}`; }
};

export default function ProductMatchingPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);
  const queryClient = useQueryClient();
  const [sortDirection, setSortDirection] = useState<ProductSortDirection>("asc");
  const [supplierId, setSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [supplierSku, setSupplierSku] = useState("");
  const [barcode, setBarcode] = useState("");
  const [price, setPrice] = useState("");
  const [unit, setUnit] = useState("");
  const [unitsPerCarton, setUnitsPerCarton] = useState("");
  const [currency, setCurrency] = useState("ILS");
  const [queryById, setQueryById] = useState<Record<number, string>>({});
  const [suggestionsById, setSuggestionsById] = useState<Record<number, MasterMatchSuggestion[]>>({});
  const [selectedById, setSelectedById] = useState<Record<number, string>>({});
  const [masterNameById, setMasterNameById] = useState<Record<number, string>>({});
  const [message, setMessage] = useState("");

  const suppliers = useQuery({ queryKey: ["catalog", "suppliers", "matching"], queryFn: () => catalogService.listSuppliers(true), enabled: canManage });
  const pending = useQuery({ queryKey: ["catalog", "supplier-products", "pending"], queryFn: catalogService.listPendingSupplierProducts, enabled: canManage, refetchInterval: 60000 });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["catalog", "supplier-products", "pending"] });
    await queryClient.invalidateQueries({ queryKey: ["catalog", "master-products"] });
  };

  const intake = useMutation({
    mutationFn: catalogService.intakeSupplierProduct,
    onSuccess: async (result) => {
      setMessage(result.supplier_product.match_status === "APPROVED"
        ? "הפריט זוהה לפי ברקוד מדויק ושויך אוטומטית למוצר האב."
        : "הפריט נקלט וממתין לאישור שיוך. התאמה לפי שם בלבד אינה מאשרת שיוך אוטומטית.");
      setSupplierName(""); setSupplierSku(""); setBarcode(""); setPrice(""); setUnit(""); setUnitsPerCarton(""); setCurrency("ILS");
      await refresh();
    },
    onError: (error: any) => setMessage(error?.response?.data?.message || "לא ניתן לקלוט את פריט הספק."),
  });
  const approve = useMutation({
    mutationFn: ({ itemId, masterId }: { itemId: number; masterId: number }) => catalogService.approveSupplierProduct(itemId, masterId),
    onSuccess: async () => { setMessage("השיוך אושר ונשמר."); await refresh(); },
    onError: (error: any) => setMessage(error?.response?.data?.message || "אישור השיוך נכשל."),
  });
  const createMaster = useMutation({
    mutationFn: ({ itemId, name }: { itemId: number; name: string }) => catalogService.createMasterAndApproveSupplierProduct(itemId, { canonical_name: name }),
    onSuccess: async () => { setMessage("מוצר האב נוצר והשיוך אושר."); await refresh(); },
    onError: (error: any) => setMessage(error?.response?.data?.message || "יצירת מוצר האב נכשלה."),
  });
  const reject = useMutation({
    mutationFn: catalogService.rejectSupplierProduct,
    onSuccess: async () => { setMessage("הצעת השיוך נדחתה."); await refresh(); },
    onError: (error: any) => setMessage(error?.response?.data?.message || "דחיית הפריט נכשלה."),
  });

  const pendingItems = useMemo(() => sortByHebrewName(pending.data || [], (item) => item.supplier_name || "", sortDirection), [pending.data, sortDirection]);
  const busy = intake.isPending || approve.isPending || createMaster.isPending || reject.isPending;

  function submitIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    if (!supplierId || !supplierName.trim()) return;
    intake.mutate({
      supplier_id: Number(supplierId), supplier_name: supplierName.trim(),
      supplier_sku: supplierSku.trim() || undefined, barcode: barcode.trim() || undefined,
      price: price.trim() ? Number(price) : undefined, currency, unit: unit.trim() || undefined,
      units_per_carton: unitsPerCarton.trim() ? Number(unitsPerCarton) : undefined,
    });
  }

  async function searchCandidates(item: SupplierProductListing) {
    try {
      const results = await catalogService.suggestMasterProducts(queryById[item.id]?.trim() || item.supplier_name, item.barcode || undefined);
      setSuggestionsById((current) => ({ ...current, [item.id]: results }));
      setSelectedById((current) => ({ ...current, [item.id]: results[0]?.master_product.id ? String(results[0].master_product.id) : "" }));
    } catch (error: any) {
      setMessage(error?.response?.data?.message || "חיפוש מוצרי האב נכשל.");
    }
  }

  if (!canManage) return <div dir="rtl" className="p-6"><h1 className="text-xl font-bold">התאמת מוצרי ספקים</h1><p className="mt-2 text-sm text-slate-600">המסך זמין למנהלי קטלוג בלבד.</p></div>;

  return <main dir="rtl" className="mx-auto max-w-7xl space-y-6 p-4 md:p-6">
    <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div><p className="text-sm font-semibold text-primary">קטלוג אחיד</p><h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">התאמת מוצרי ספקים</h1><p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">כל ספק יכול לשמור את השם והמק״ט שלו. מוצר האב הוא הזהות המשותפת; שיוך לפי דמיון בשם דורש אישור אנושי.</p></div>
      <Button variant="secondary" onClick={() => void refresh()} disabled={busy}><RefreshCw size={16} />רענון</Button>
    </header>

    {message && <div role="status" className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"><CircleHelp size={17} className="mt-0.5 shrink-0" />{message}</div>}

    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 md:p-5">
      <div className="mb-4 flex items-center gap-2"><Plus size={18} className="text-primary" /><h2 className="font-bold">קליטת פריט ממחירון ספק</h2></div>
      <form onSubmit={submitIntake} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className="space-y-1 text-sm"><span className="font-medium">ספק *</span><Select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} required><option value="">בחר ספק</option>{(suppliers.data || []).map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</Select></label>
        <label className="space-y-1 text-sm"><span className="font-medium">שם המוצר אצל הספק *</span><Input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} required placeholder="למשל: חלב טרי תנובה 3 אחוז ליטר" /></label>
        <label className="space-y-1 text-sm"><span className="font-medium">מק״ט ספק</span><Input value={supplierSku} onChange={(e) => setSupplierSku(e.target.value)} placeholder="מק״ט כפי שמופיע במחירון" /></label>
        <label className="space-y-1 text-sm"><span className="font-medium">ברקוד</span><Input value={barcode} onChange={(e) => setBarcode(e.target.value)} /></label>
        <label className="space-y-1 text-sm"><span className="font-medium">מחיר נוכחי</span><Input type="number" min="0.01" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="מחיר חיובי בלבד" /></label>
        <label className="space-y-1 text-sm"><span className="font-medium">מטבע</span><Select value={currency} onChange={(e) => setCurrency(e.target.value)}><option value="ILS">שקל (ILS)</option><option value="USD">דולר (USD)</option><option value="EUR">אירו (EUR)</option></Select></label>
        <label className="space-y-1 text-sm"><span className="font-medium">יחידת מכירה</span><Input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="ליטר, ק״ג, יחידה, קרטון..." /></label>
        <label className="space-y-1 text-sm"><span className="font-medium">יחידות בקרטון / ארגז</span><Input type="number" min="1" step="1" value={unitsPerCarton} onChange={(e) => setUnitsPerCarton(e.target.value)} placeholder="רק אם המחיר לקרטון" /></label>
        <div className="sm:col-span-2 lg:col-span-3"><Button type="submit" disabled={busy || !supplierId || !supplierName.trim()}><Plus size={16} />קליטת פריט והצעת התאמה</Button></div>
      </form>
      <p className="mt-3 text-xs text-slate-500">ברקוד זהה ותקין עשוי לאפשר שיוך אוטומטי. התאמה טקסטואלית מוצגת כהצעה בלבד; הבדלי נפח או אחוזים מונעים התאמה.</p>
    </section>

    <section className="space-y-3">
      <div className="flex items-center justify-between"><div><h2 className="text-lg font-bold">תור אישורי התאמה</h2><p className="text-sm text-slate-500">פריטים שעדיין לא שויכו למוצר אב</p></div><span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">{pendingItems.length} ממתינים</span></div>
      {pending.isLoading && <div className="flex items-center gap-2 rounded-xl border border-slate-200 p-6 text-sm text-slate-500"><Loader2 className="animate-spin" size={18} />טוען פריטים...</div>}
      {pending.isError && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">לא ניתן לטעון את תור האישור. בדוק הרשאות או רענן את המסך.</div>}
      {!pending.isLoading && !pending.isError && pendingItems.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center"><Check className="mx-auto mb-2 text-emerald-600" size={28} /><p className="font-semibold">אין פריטים שממתינים לאישור</p><p className="mt-1 text-sm text-slate-500">פריטים חדשים שיובאו ממחירוני ספקים יופיעו כאן אם לא ניתן לזהות אותם בבטחה.</p></div>}
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-slate-500">פריטים ממתינים ממוינים לפי שם א׳–ת׳.</p><ProductSortToggle direction={sortDirection} onToggle={() => setSortDirection((current) => current === "asc" ? "desc" : "asc")} /></div>
      {pendingItems.map((item) => {
        const suggestions = sortByHebrewName(suggestionsById[item.id] || [], (suggestion) => suggestion.master_product.canonical_name || "", sortDirection);
        const selectedId = Number(selectedById[item.id] || item.suggested_master_product_id || 0);
        return <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div>
              <div className="flex flex-wrap items-center gap-2"><h3 className="text-base font-bold">{item.supplier_name}</h3><span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">{item.supplier_company_name || `ספק #${item.supplier_id}`}</span></div>
              <div className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-300"><p>מק״ט: {item.supplier_sku || "לא צוין"} · ברקוד: {item.barcode || "לא צוין"}</p><p>מחיר: {money(item.price, item.currency)} · יחידה: {item.unit || "לא צוינה"}</p><p className="text-xs text-slate-400">הצעה אחרונה: {item.match_confidence != null ? `${Math.round(item.match_confidence * 100)}% · ${item.match_method || "התאמת שם"}` : "לא נמצאה התאמה מספקת"}</p></div>
            </div>
            <div className="space-y-3">
              <label className="block space-y-1 text-sm"><span className="font-medium">חפש מוצר אב קיים</span><div className="flex gap-2"><Input value={queryById[item.id] || ""} onChange={(e) => setQueryById((current) => ({ ...current, [item.id]: e.target.value }))} placeholder="שם מוצר, מותג או ברקוד" /><Button variant="secondary" onClick={() => void searchCandidates(item)} disabled={busy}><Search size={15} />חיפוש</Button></div></label>
              {(suggestions.length > 0 || item.suggested_master_product) && <div className="space-y-2 rounded-xl bg-slate-50 p-3 dark:bg-slate-900">
                {suggestions.length === 0 && item.suggested_master_product && <p className="text-sm">הצעה: <strong>{item.suggested_master_product.canonical_name}</strong></p>}
                {suggestions.map((suggestion) => <label key={suggestion.master_product.id} className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 bg-white p-2 text-sm dark:border-slate-700 dark:bg-slate-950"><input type="radio" name={`master-${item.id}`} checked={selectedId === suggestion.master_product.id} onChange={() => setSelectedById((current) => ({ ...current, [item.id]: String(suggestion.master_product.id) }))} className="mt-1" /><span className="min-w-0 flex-1"><span className="block font-semibold">{suggestion.master_product.canonical_name}</span><span className="text-xs text-slate-500">{Math.round(suggestion.confidence * 100)}% התאמה · {suggestion.method}</span></span></label>)}
                <Button onClick={() => approve.mutate({ itemId: item.id, masterId: selectedId })} disabled={busy || !selectedId}><Check size={15} />אישור שיוך למוצר האב</Button>
              </div>}
              <div className="flex flex-col gap-2 sm:flex-row"><Input value={masterNameById[item.id] ?? item.supplier_name} onChange={(e) => setMasterNameById((current) => ({ ...current, [item.id]: e.target.value }))} aria-label="שם קנוני למוצר האב" placeholder="שם אחיד למוצר האב" /><Button variant="secondary" onClick={() => createMaster.mutate({ itemId: item.id, name: (masterNameById[item.id] ?? item.supplier_name).trim() })} disabled={busy || !(masterNameById[item.id] ?? item.supplier_name).trim()}><Plus size={15} />יצירת מוצר אב</Button><Button variant="danger" onClick={() => reject.mutate(item.id)} disabled={busy}><X size={15} />דחייה</Button></div>
            </div>
          </div>
        </article>;
      })}
    </section>
    <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"><AlertTriangle size={16} className="mt-0.5 shrink-0" /><p>האישור משפיע על שכבת הקטלוג האחיד החדשה בלבד. הזמנות קיימות והיסטוריית מחירים לא משתנות, ואין מיזוג אוטומטי של מוצרים קיימים על סמך דמיון בשם.</p></div>
  </main>;
}
