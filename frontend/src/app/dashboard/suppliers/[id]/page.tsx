"use client";

import { use, useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, Check, ChevronLeft, Loader2, Search, ShoppingCart, Truck, ImageOff, Info, Save } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useSupplier, useUpdateSupplier, useProducts } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from "@/components/ui/table";
import { ProductSortToggle } from "@/components/catalog/product-sort-toggle";
import { sortByHebrewName, type ProductSortDirection } from "@/lib/product-sorting";

const WEEK_DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"] as const;
type WeekDay = (typeof WEEK_DAYS)[number];

function parseDays(value?: string | null): WeekDay[] {
  if (!value) return [];
  const aliases: Record<string, WeekDay> = {
    "א": "ראשון", "א׳": "ראשון", "ראשון": "ראשון",
    "ב": "שני", "ב׳": "שני", "שני": "שני",
    "ג": "שלישי", "ג׳": "שלישי", "שלישי": "שלישי",
    "ד": "רביעי", "ד׳": "רביעי", "רביעי": "רביעי",
    "ה": "חמישי", "ה׳": "חמישי", "חמישי": "חמישי",
    "ו": "שישי", "ו׳": "שישי", "שישי": "שישי",
    "ש": "שבת", "ש׳": "שבת", "שבת": "שבת",
  };

  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) value = parsed.join(",");
  } catch {
    // Existing installations store days as comma-separated Hebrew text.
  }

  const selected = new Set<WeekDay>();
  value
    .split(/[,,|;/]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      const day = aliases[part] ?? aliases[part.replace(/[׳']/g, "")];
      if (day) selected.add(day);
    });

  return WEEK_DAYS.filter((day) => selected.has(day));
}

function serializeDays(days: WeekDay[]) {
  return WEEK_DAYS.filter((day) => days.includes(day)).join(", ");
}

function DaySelector({
  title,
  description,
  icon,
  selected,
  onChange,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  selected: WeekDay[];
  onChange: (days: WeekDay[]) => void;
}) {
  const toggle = (day: WeekDay) => {
    onChange(selected.includes(day) ? selected.filter((item) => item !== day) : [...selected, day]);
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-800">
        <div className="flex items-center gap-2 text-slate-900 dark:text-white">
          <span className="text-indigo-600 dark:text-indigo-400">{icon}</span>
          <h2 className="font-bold">{title}</h2>
        </div>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7">
        {WEEK_DAYS.map((day) => {
          const active = selected.includes(day);
          return (
            <button
              key={day}
              type="button"
              onClick={() => toggle(day)}
              aria-pressed={active}
              className={`group flex min-h-[92px] flex-col items-center justify-center gap-3 border-b border-l border-slate-100 px-3 transition last:border-l-0 hover:bg-indigo-50/70 dark:border-slate-800 dark:hover:bg-indigo-950/30 ${active ? "bg-indigo-50 dark:bg-indigo-950/40" : "bg-white dark:bg-slate-900"}`}
            >
              <span className={`text-sm font-bold ${active ? "text-indigo-700 dark:text-indigo-300" : "text-slate-600 dark:text-slate-300"}`}>{day}</span>
              <span className={`flex h-7 w-7 items-center justify-center rounded-md border-2 transition ${active ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white text-transparent dark:border-slate-600 dark:bg-slate-950"}`}>
                <Check size={16} strokeWidth={3} />
              </span>
            </button>
          );
        })}
      </div>
      <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500 dark:border-slate-800">
        {selected.length ? `נבחרו ${selected.length} ימים: ${selected.join(" · ")}` : "לא נבחרו ימים"}
      </div>
    </section>
  );
}

function PreviewCard({
  supplierName,
  active,
  orderDays,
  deliveryDays,
  phone,
  contact,
  customerNumber,
}: {
  supplierName: string;
  active: boolean;
  orderDays: WeekDay[];
  deliveryDays: WeekDay[];
  phone: string;
  contact: string;
  customerNumber: string;
}) {
  return (
    <Card className="overflow-hidden border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader className="border-b border-slate-100 dark:border-slate-800">
        <CardTitle className="flex items-center gap-2 text-base">
          <Info size={17} className="text-slate-500" />
          תצוגה מקדימה
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-5">
        <div>
          <div className="text-lg font-extrabold text-slate-900 dark:text-white">{supplierName || "ספק חדש"}</div>
          <div className="mt-2"><ActiveBadge active={active} /></div>
        </div>
        <div className="space-y-3 text-sm">
          <div><div className="text-xs text-slate-400">איש קשר</div><div className="font-medium">{contact || "—"}</div></div>
          <div><div className="text-xs text-slate-400">טלפון</div><div className="font-medium">{phone || "—"}</div></div>
          <div><div className="text-xs text-slate-400">מס׳ לקוח</div><div className="font-medium">{customerNumber || "—"}</div></div>
        </div>
        <div className="border-t border-slate-100 pt-4 dark:border-slate-800">
          <div className="text-sm font-bold">ימי הזמנות</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {orderDays.length ? orderDays.map((day) => <span key={day} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">{day}</span>) : <span className="text-xs text-slate-400">לא הוגדרו</span>}
          </div>
        </div>
        <div>
          <div className="text-sm font-bold">ימי אספקה</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {deliveryDays.length ? deliveryDays.map((day) => <span key={day} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">{day}</span>) : <span className="text-xs text-slate-400">לא הוגדרו</span>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SupplierDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const supplierId = Number(id);
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);
  const { data: supplier, isLoading, isError } = useSupplier(supplierId);
  const { data: products } = useProducts(supplierId);
  const updateSupplier = useUpdateSupplier(supplierId);

  const [sortDirection, setSortDirection] = useState<ProductSortDirection>("asc");
  const [search, setSearch] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState({ name: "", contact_name: "", email: "", phone: "", phone2: "", mobile: "", customer_number: "", address: "", city: "", tax_id: "", website: "", supplier_category: "", payment_terms: "", credit_days: "", minimum_order_amount: "", delivery_fee: "", lead_time_days: "", order_cutoff_time: "", certification_details: "", notes: "", order_days: [] as WeekDay[], delivery_days: [] as WeekDay[], active: true });

  const filteredProducts = useMemo(() => {
    if (!products) return [];
    const q = search.toLowerCase();
    const matches = !search ? products : products.filter((p) => p.name.toLowerCase().includes(q) || (p.sku ?? "").toLowerCase().includes(q));
    return sortByHebrewName(matches, (product) => product.name, sortDirection);
  }, [products, search, sortDirection]);

  useEffect(() => {
    if (supplier) {
      setForm({
        name: supplier.name,
        contact_name: supplier.contact_name ?? "",
        email: supplier.email ?? "",
        phone: supplier.phone ?? "",
        phone2: supplier.phone2 ?? "",
        mobile: supplier.mobile ?? "",
        customer_number: supplier.customer_number ?? "",
        address: supplier.address ?? "",
        city: supplier.city ?? "",
        tax_id: supplier.tax_id ?? "",
        website: supplier.website ?? "",
        supplier_category: supplier.supplier_category ?? "",
        payment_terms: supplier.payment_terms ?? "",
        credit_days: supplier.credit_days == null ? "" : String(supplier.credit_days),
        minimum_order_amount: supplier.minimum_order_amount == null ? "" : String(supplier.minimum_order_amount),
        delivery_fee: supplier.delivery_fee == null ? "" : String(supplier.delivery_fee),
        lead_time_days: supplier.lead_time_days == null ? "" : String(supplier.lead_time_days),
        order_cutoff_time: supplier.order_cutoff_time ?? "",
        certification_details: supplier.certification_details ?? "",
        notes: supplier.notes ?? "",
        order_days: parseDays(supplier.order_days),
        delivery_days: parseDays(supplier.delivery_days),
        active: supplier.active,
      });
    }
  }, [supplier]);

  if (isLoading) return <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="animate-spin" size={16} />טוען ספק...</div>;
  if (isError || !supplier) return <p className="text-sm text-slate-400">הספק לא נמצא</p>;

  const save = () => {
    updateSupplier.mutate({
      name: form.name,
      contact_name: form.contact_name,
      email: form.email,
      phone: form.phone,
      phone2: form.phone2,
      mobile: form.mobile,
      customer_number: form.customer_number,
      address: form.address,
      city: form.city,
      tax_id: form.tax_id,
      website: form.website,
      supplier_category: form.supplier_category,
      payment_terms: form.payment_terms,
      credit_days: form.credit_days.trim() ? Number(form.credit_days) : null,
      minimum_order_amount: form.minimum_order_amount.trim() ? Number(form.minimum_order_amount) : null,
      delivery_fee: form.delivery_fee.trim() ? Number(form.delivery_fee) : null,
      lead_time_days: form.lead_time_days.trim() ? Number(form.lead_time_days) : null,
      order_cutoff_time: form.order_cutoff_time,
      certification_details: form.certification_details,
      notes: form.notes,
      order_days: serializeDays(form.order_days),
      delivery_days: serializeDays(form.delivery_days),
      active: form.active,
    }, { onSuccess: () => setIsEditing(false) });
  };

  const toggleActive = () => updateSupplier.mutate({ active: !supplier.active });

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <Link href="/dashboard" className="hover:text-slate-900 dark:hover:text-white">ראשי</Link>
        <ChevronLeft size={15} />
        <Link href="/dashboard/suppliers" className="hover:text-slate-900 dark:hover:text-white">ספקים</Link>
        <ChevronLeft size={15} />
        <span className="font-medium text-slate-700 dark:text-slate-200">עריכת ספק</span>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">{isEditing ? "עריכת ספק" : supplier.name}</h1>
          <p className="mt-1 text-sm text-slate-500">ניהול פרטי הספק, ימי הזמנות וימי אספקה</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/dashboard/suppliers"><Button variant="ghost"><ArrowLeft size={16} />חזרה</Button></Link>
          {canManage && !isEditing && <>
            <Link href={`/dashboard/orders/new?supplier_id=${supplier.id}`}><Button variant="secondary"><ShoppingCart size={16} />הזמנה חדשה</Button></Link>
            <Button variant="secondary" onClick={() => setIsEditing(true)}>עריכה</Button>
            <Button variant={supplier.active ? "danger" : "primary"} onClick={toggleActive} disabled={updateSupplier.isPending}>{supplier.active ? "השבתה" : "הפעלה"}</Button>
          </>}
        </div>
      </div>

      {isEditing ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <Card className="border-slate-200 shadow-sm dark:border-slate-800">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800"><CardTitle className="flex items-center gap-2 text-base"><Info size={17} className="text-slate-500" />פרטי ספק</CardTitle></CardHeader>
              <CardContent className="grid gap-5 pt-6 sm:grid-cols-2">
                <div><label className="mb-1.5 block text-sm font-semibold">שם ספק <span className="text-red-500">*</span></label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">טלפון <span className="text-red-500">*</span></label><Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">איש קשר</label><Input value={form.contact_name} onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">טלפון נוסף</label><Input value={form.phone2} onChange={(e) => setForm((f) => ({ ...f, phone2: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">מס׳ לקוח</label><Input value={form.customer_number} onChange={(e) => setForm((f) => ({ ...f, customer_number: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">אימייל</label><Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">נייד</label><Input value={form.mobile} onChange={(e) => setForm((f) => ({ ...f, mobile: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">כתובת</label><Input value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">עיר</label><Input value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">ח.פ. / עוסק מורשה</label><Input value={form.tax_id} onChange={(e) => setForm((f) => ({ ...f, tax_id: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">אתר אינטרנט</label><Input value={form.website} onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))} placeholder="https://..." /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">קטגוריית ספק</label><Input value={form.supplier_category} onChange={(e) => setForm((f) => ({ ...f, supplier_category: e.target.value }))} placeholder="למשל: מזון, ניקיון, ציוד" /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">תנאי תשלום</label><Input value={form.payment_terms} onChange={(e) => setForm((f) => ({ ...f, payment_terms: e.target.value }))} placeholder="למשל: שוטף + 30" /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">ימי אשראי</label><Input type="number" min="0" value={form.credit_days} onChange={(e) => setForm((f) => ({ ...f, credit_days: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">מינימום הזמנה (₪)</label><Input type="number" min="0" step="0.01" value={form.minimum_order_amount} onChange={(e) => setForm((f) => ({ ...f, minimum_order_amount: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">דמי משלוח (₪)</label><Input type="number" min="0" step="0.01" value={form.delivery_fee} onChange={(e) => setForm((f) => ({ ...f, delivery_fee: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">זמן אספקה משוער (ימים)</label><Input type="number" min="0" value={form.lead_time_days} onChange={(e) => setForm((f) => ({ ...f, lead_time_days: e.target.value }))} /></div>
                <div><label className="mb-1.5 block text-sm font-semibold">שעת סגירת הזמנות</label><Input type="time" value={form.order_cutoff_time} onChange={(e) => setForm((f) => ({ ...f, order_cutoff_time: e.target.value }))} /></div>
                <div className="sm:col-span-2"><label className="mb-1.5 block text-sm font-semibold">כשרות / תעודות / תקנים</label><Input value={form.certification_details} onChange={(e) => setForm((f) => ({ ...f, certification_details: e.target.value }))} placeholder="פרטים כפי שאומתו מול הספק" /></div>
                <div className="sm:col-span-2"><label className="mb-1.5 block text-sm font-semibold">הערות פנימיות</label><textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} rows={3} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950" /></div>
                <div className="sm:col-span-2"><label className="mb-1.5 block text-sm font-semibold">סטטוס</label><label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700"><input type="checkbox" checked={form.active} onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))} className="h-4 w-4 accent-indigo-600" /><span className="text-sm font-medium">ספק פעיל</span></label></div>
              </CardContent>
            </Card>

            <DaySelector title="ימי הזמנות" description="בחר את הימים שבהם ניתן לבצע הזמנות מספק זה" icon={<ShoppingCart size={18} />} selected={form.order_days} onChange={(days) => setForm((f) => ({ ...f, order_days: days }))} />
            <DaySelector title="ימי אספקה" description="בחר את הימים שבהם הספק מבצע אספקות" icon={<Truck size={18} />} selected={form.delivery_days} onChange={(days) => setForm((f) => ({ ...f, delivery_days: days }))} />

            <div className="flex flex-wrap gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <Button onClick={save} disabled={updateSupplier.isPending || !form.name.trim()}>{updateSupplier.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}{updateSupplier.isPending ? "שומר..." : "שמור שינויים"}</Button>
              <Button variant="ghost" onClick={() => setIsEditing(false)} disabled={updateSupplier.isPending}>ביטול</Button>
            </div>
          </div>

          <PreviewCard supplierName={form.name} active={form.active} orderDays={form.order_days} deliveryDays={form.delivery_days} phone={form.phone} contact={form.contact_name} customerNumber={form.customer_number} />
        </div>
      ) : (
        <>
          <Card className="border-slate-200 shadow-sm dark:border-slate-800">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800"><CardTitle className="text-base">פרטי ספק</CardTitle></CardHeader>
            <CardContent className="grid gap-5 pt-6 sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-xs text-slate-500">איש קשר</dt><dd className="mt-1 font-medium">{supplier.contact_name || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">אימייל</dt><dd className="mt-1 font-medium">{supplier.email || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">טלפון</dt><dd className="mt-1 font-medium">{supplier.phone || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">טלפון נוסף</dt><dd className="mt-1 font-medium">{supplier.phone2 || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">נייד</dt><dd className="mt-1 font-medium">{supplier.mobile || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">מס׳ לקוח</dt><dd className="mt-1 font-medium">{supplier.customer_number || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">כתובת</dt><dd className="mt-1 font-medium">{[supplier.address, supplier.city].filter(Boolean).join(", ") || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">ח.פ. / עוסק מורשה</dt><dd className="mt-1 font-medium">{supplier.tax_id || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">אתר אינטרנט</dt><dd className="mt-1 font-medium">{supplier.website ? <a href={supplier.website.startsWith("http://") || supplier.website.startsWith("https://") ? supplier.website : "https://" + supplier.website} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">{supplier.website}</a> : "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">קטגוריית ספק</dt><dd className="mt-1 font-medium">{supplier.supplier_category || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">תנאי תשלום</dt><dd className="mt-1 font-medium">{supplier.payment_terms || "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">ימי אשראי</dt><dd className="mt-1 font-medium">{supplier.credit_days ?? "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">מינימום הזמנה</dt><dd className="mt-1 font-medium">{supplier.minimum_order_amount != null ? `₪${Number(supplier.minimum_order_amount).toLocaleString("he-IL", {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">דמי משלוח</dt><dd className="mt-1 font-medium">{supplier.delivery_fee != null ? `₪${Number(supplier.delivery_fee).toLocaleString("he-IL", {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">זמן אספקה משוער</dt><dd className="mt-1 font-medium">{supplier.lead_time_days != null ? `${supplier.lead_time_days} ימים` : "—"}</dd></div>
              <div><dt className="text-xs text-slate-500">שעת סגירת הזמנות</dt><dd className="mt-1 font-medium">{supplier.order_cutoff_time || "—"}</dd></div>
              <div className="sm:col-span-2 lg:col-span-4"><dt className="text-xs text-slate-500">כשרות / תעודות / תקנים</dt><dd className="mt-1 whitespace-pre-wrap font-medium">{supplier.certification_details || "לא הוזן מידע מאומת"}</dd></div>
              <div className="sm:col-span-2 lg:col-span-4"><dt className="text-xs text-slate-500">הערות פנימיות</dt><dd className="mt-1 whitespace-pre-wrap font-medium">{supplier.notes || "—"}</dd></div>
              <div className="lg:col-span-2"><dt className="text-xs text-slate-500">ימי הזמנות</dt><dd className="mt-2 flex flex-wrap gap-1.5">{parseDays(supplier.order_days).map((day) => <span key={day} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">{day}</span>)}{!parseDays(supplier.order_days).length && <span className="text-sm text-slate-400">לא הוגדרו</span>}</dd></div>
              <div className="lg:col-span-2"><dt className="text-xs text-slate-500">ימי אספקה</dt><dd className="mt-2 flex flex-wrap gap-1.5">{parseDays(supplier.delivery_days).map((day) => <span key={day} className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">{day}</span>)}{!parseDays(supplier.delivery_days).length && <span className="text-sm text-slate-400">לא הוגדרו</span>}</dd></div>
            </CardContent>
          </Card>
        </>
      )}

      <Card className="border-slate-200 shadow-sm dark:border-slate-800">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800"><CardTitle className="text-base">מוצרים מספק זה</CardTitle></CardHeader>
        <CardContent className="space-y-4 pt-5">
          {products && products.length > 0 && <div className="relative max-w-sm"><Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><Input placeholder="חיפוש מוצר..." value={search} onChange={(e) => setSearch(e.target.value)} className="pr-9" /></div>}
          {!products || products.length === 0 ? <p className="text-sm text-slate-400">אין מוצרים עדיין.</p> : filteredProducts.length === 0 ? <p className="text-sm text-slate-400">לא נמצאו מוצרים התואמים לחיפוש.</p> : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <div className="mb-3 flex justify-end"><ProductSortToggle direction={sortDirection} onToggle={() => setSortDirection((current) => current === "asc" ? "desc" : "asc")} /></div><Table><TableHead><tr><TableHeaderCell></TableHeaderCell><TableHeaderCell>מק"ט</TableHeaderCell><TableHeaderCell>שם</TableHeaderCell><TableHeaderCell>קטגוריה</TableHeaderCell><TableHeaderCell>יחידה</TableHeaderCell><TableHeaderCell>מחיר</TableHeaderCell><TableHeaderCell>סטטוס</TableHeaderCell></tr></TableHead><TableBody>{filteredProducts.map((p) => <TableRow key={p.id}>
                <TableCell>{p.image_url ? <img src={p.image_url} alt={p.name} className="h-8 w-8 rounded object-cover bg-slate-100" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} /> : <div className="flex h-8 w-8 items-center justify-center rounded bg-slate-100 text-slate-300"><ImageOff size={14} /></div>}</TableCell>
                <TableCell className="text-slate-500">{p.sku || "—"}</TableCell><TableCell className="font-medium">{p.name}</TableCell><TableCell className="text-slate-500">{p.category || "—"}</TableCell><TableCell className="text-slate-500">{p.unit || "—"}</TableCell><TableCell>{p.current_price != null && p.current_price > 0 ? `${p.currency} ${p.current_price.toLocaleString()}` : "חסר מחיר"}</TableCell><TableCell><ActiveBadge active={p.active} /></TableCell>
              </TableRow>)}</TableBody></Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
