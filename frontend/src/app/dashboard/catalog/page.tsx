"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  Grid2X2,
  ImageOff,
  Package,
  Pencil,
  Plus,
  Power,
  Save,
  Search,
  X,
} from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import {
  useCreateProduct,
  useProducts,
  useSuppliers,
  useToggleProductActive,
  useUpdateProduct,
} from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ActiveBadge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PriceComparison } from "@/components/catalog/price-comparison";
import { Product } from "@/types";

interface ProductFormState {
  supplier_id: string;
  name: string;
  sku: string;
  description: string;
  current_price: string;
  currency: string;
  image_url: string;
  barcode: string;
  category: string;
  unit: string;
  units_per_carton: string;
  supplier_sku: string;
  current_stock: string;
  min_stock: string;
  recommended_stock: string;
}

type ViewMode = "list" | "grid";
type InlineField = "name" | "current_price" | "current_stock";

const EMPTY_FORM: ProductFormState = {
  supplier_id: "",
  name: "",
  sku: "",
  description: "",
  current_price: "",
  currency: "ILS",
  image_url: "",
  barcode: "",
  category: "",
  unit: "",
  units_per_carton: "",
  supplier_sku: "",
  current_stock: "",
  min_stock: "",
  recommended_stock: "",
};

function parseOptionalInt(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : undefined;
}

function stockPercent(product: Product): number | null {
  if (product.current_stock == null || product.min_stock == null) return null;
  const target = product.recommended_stock ?? product.min_stock;
  if (target <= 0) return 100;
  return Math.max(0, Math.min(100, (product.current_stock / target) * 100));
}

function stockTone(product: Product) {
  if (product.current_stock == null || product.min_stock == null) return "neutral";
  if (product.current_stock < product.min_stock) return "danger";
  if (product.recommended_stock != null && product.current_stock < product.recommended_stock) return "warning";
  return "healthy";
}

export default function CatalogPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [modalOpen, setModalOpen] = useState(false);
  const [showMoreFields, setShowMoreFields] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [inlineEdit, setInlineEdit] = useState<{ id: number; field: InlineField; value: string } | null>(null);

  const { data: products, isLoading, isError, refetch } = useProducts();
  const { data: suppliers } = useSuppliers();
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct(inlineEdit?.id ?? editingProduct?.id ?? -1);
  const toggleActive = useToggleProductActive(editingProduct?.id ?? -1);

  const supplierName = (supplierId: number) =>
    suppliers?.find((s) => s.id === supplierId)?.name ?? `#${supplierId}`;

  const categories = useMemo(() => {
    const set = new Set<string>();
    products?.forEach((p) => {
      if (p.category) set.add(p.category);
    });
    return Array.from(set).sort();
  }, [products]);

  const filtered = useMemo(() => {
    if (!products) return [];
    const query = search.trim().toLowerCase();
    return products.filter((p) => {
      const matchesSearch =
        !query ||
        p.name.toLowerCase().includes(query) ||
        (p.sku ?? "").toLowerCase().includes(query) ||
        (p.barcode ?? "").includes(query) ||
        supplierName(p.supplier_id).toLowerCase().includes(query);
      const matchesStatus =
        statusFilter === "all" || (statusFilter === "active" ? p.active : !p.active);
      const matchesCategory = categoryFilter === "all" || p.category === categoryFilter;
      return matchesSearch && matchesStatus && matchesCategory;
    });
  }, [products, search, statusFilter, categoryFilter, suppliers]);

  const isLowStock = (p: Product) =>
    p.current_stock != null && p.min_stock != null && p.current_stock < p.min_stock;

  const openCreateModal = () => {
    setEditingProduct(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowMoreFields(false);
    setModalOpen(true);
  };

  const openEditModal = (product: Product) => {
    setEditingProduct(product);
    setForm({
      supplier_id: String(product.supplier_id),
      name: product.name,
      sku: product.sku ?? "",
      description: product.description ?? "",
      current_price: String(product.current_price),
      currency: product.currency,
      image_url: product.image_url ?? "",
      barcode: product.barcode ?? "",
      category: product.category ?? "",
      unit: product.unit ?? "",
      units_per_carton: product.units_per_carton != null ? String(product.units_per_carton) : "",
      supplier_sku: product.supplier_sku ?? "",
      current_stock: product.current_stock != null ? String(product.current_stock) : "",
      min_stock: product.min_stock != null ? String(product.min_stock) : "",
      recommended_stock: product.recommended_stock != null ? String(product.recommended_stock) : "",
    });
    setFormError(null);
    setShowMoreFields(false);
    setModalOpen(true);
  };

  const startInlineEdit = (product: Product, field: InlineField) => {
    const value = field === "name"
      ? product.name
      : field === "current_price"
        ? String(product.current_price)
        : product.current_stock == null
          ? ""
          : String(product.current_stock);
    setInlineEdit({ id: product.id, field, value });
  };

  const cancelInlineEdit = () => setInlineEdit(null);

  const saveInlineEdit = () => {
    if (!inlineEdit) return;
    const value = inlineEdit.value.trim();
    if (inlineEdit.field === "name") {
      if (!value) return;
      updateProduct.mutate({ name: value }, { onSuccess: () => setInlineEdit(null) });
      return;
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 0) return;
    if (inlineEdit.field === "current_price") {
      updateProduct.mutate({ current_price: numeric }, { onSuccess: () => setInlineEdit(null) });
    } else {
      updateProduct.mutate({ current_stock: Math.trunc(numeric) }, { onSuccess: () => setInlineEdit(null) });
    }
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!form.supplier_id) return setFormError("בחר ספק.");
    if (!form.name.trim()) return setFormError("שם המוצר הוא שדה חובה.");
    const price = Number(form.current_price);
    if (!Number.isFinite(price) || price < 0) return setFormError("הזן מחיר תקין.");
    if (form.barcode.trim() && !/^\d+$/.test(form.barcode.trim())) {
      return setFormError("ברקוד יכול להכיל ספרות בלבד.");
    }
    for (const [label, value] of [
      ["יחידות בקרטון", form.units_per_carton],
      ["מלאי קיים", form.current_stock],
      ["מלאי מינימום", form.min_stock],
      ["מלאי מומלץ", form.recommended_stock],
    ] as const) {
      if (value.trim() && (!Number.isFinite(Number(value)) || Number(value) < 0)) {
        return setFormError(`${label}: יש להזין מספר שלם חיובי.`);
      }
    }

    const payload = {
      supplier_id: Number(form.supplier_id),
      name: form.name.trim(),
      sku: form.sku.trim() || undefined,
      description: form.description.trim() || undefined,
      current_price: price,
      currency: form.currency,
      image_url: form.image_url.trim() || undefined,
      barcode: form.barcode.trim() || undefined,
      category: form.category.trim() || undefined,
      unit: form.unit.trim() || undefined,
      units_per_carton: parseOptionalInt(form.units_per_carton),
      supplier_sku: form.supplier_sku.trim() || undefined,
      current_stock: parseOptionalInt(form.current_stock),
      min_stock: parseOptionalInt(form.min_stock),
      recommended_stock: parseOptionalInt(form.recommended_stock),
    };

    if (editingProduct) {
      updateProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    } else {
      createProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    }
  };

  const isSaving = createProduct.isPending || updateProduct.isPending;
  const inputClass =
    "block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-primary focus:ring-2 focus:ring-primary/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

  const renderInlineCell = (product: Product, field: InlineField, display: React.ReactNode) => {
    const active = inlineEdit?.id === product.id && inlineEdit.field === field;
    if (!active) {
      return (
        <button
          type="button"
          onDoubleClick={() => canManage && startInlineEdit(product, field)}
          className={canManage ? "w-full rounded-lg px-1.5 py-1 text-right transition hover:bg-slate-100 dark:hover:bg-slate-800" : "w-full text-right"}
          title={canManage ? "לחיצה כפולה לעריכה מהירה" : undefined}
        >
          {display}
        </button>
      );
    }
    return (
      <div className="flex items-center gap-1.5">
        <Input
          autoFocus
          value={inlineEdit.value}
          type={field === "name" ? "text" : "number"}
          min={field === "name" ? undefined : 0}
          step={field === "current_price" ? "0.01" : "1"}
          onChange={(e) => setInlineEdit((current) => current ? { ...current, value: e.target.value } : current)}
          onKeyDown={(e) => {
            if (e.key === "Enter") saveInlineEdit();
            if (e.key === "Escape") cancelInlineEdit();
          }}
          className="h-9 min-w-0"
        />
        <button type="button" onClick={saveInlineEdit} className="rounded-md p-1.5 text-emerald-600 hover:bg-emerald-50" aria-label="שמירה">
          <Save size={15} />
        </button>
        <button type="button" onClick={cancelInlineEdit} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100" aria-label="ביטול">
          <X size={15} />
        </button>
      </div>
    );
  };

  const renderStock = (product: Product, compact = false) => {
    const percent = stockPercent(product);
    const tone = stockTone(product);
    const toneClass = tone === "danger" ? "bg-red-500" : tone === "warning" ? "bg-amber-400" : tone === "healthy" ? "bg-emerald-500" : "bg-slate-300";
    return (
      <div className={compact ? "min-w-0" : "min-w-[120px]"}>
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className={isLowStock(product) ? "font-bold text-red-600" : "font-semibold text-slate-700 dark:text-slate-200"}>
            {product.current_stock != null ? product.current_stock : "—"}
          </span>
          {product.min_stock != null && <span className="text-[11px] text-slate-400">מינ׳ {product.min_stock}</span>}
        </div>
        {percent != null && (
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div className={`h-full rounded-full transition-all ${toneClass}`} style={{ width: `${percent}%` }} />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">קטלוג</h1>
            {products && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500 dark:bg-slate-800">{products.length} מוצרים</span>}
          </div>
          <p className="mt-1 text-sm text-slate-500">ניהול מוצרים, מחירים ומלאי במקום אחד.</p>
        </div>
        {canManage && (
          <Button onClick={openCreateModal} className="shadow-sm">
            <Plus size={16} />
            מוצר חדש
          </Button>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <Input
              placeholder='חיפוש לפי מוצר, מק"ט, ברקוד או ספק...'
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 pr-9"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {categories.length > 0 && (
              <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="h-10 w-44">
                <option value="all">כל הקטגוריות</option>
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </Select>
            )}
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} className="h-10 w-40">
              <option value="all">כל הסטטוסים</option>
              <option value="active">פעילים בלבד</option>
              <option value="inactive">לא פעילים בלבד</option>
            </Select>
            <div className="flex h-10 rounded-lg border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-800">
              <button type="button" onClick={() => setViewMode("list")} className={`rounded-md px-2.5 ${viewMode === "list" ? "bg-white text-indigo-600 shadow-sm dark:bg-slate-700" : "text-slate-400"}`} aria-label="תצוגת רשימה">
                <span className="text-sm font-bold">☷</span>
              </button>
              <button type="button" onClick={() => setViewMode("grid")} className={`rounded-md px-2.5 ${viewMode === "grid" ? "bg-white text-indigo-600 shadow-sm dark:bg-slate-700" : "text-slate-400"}`} aria-label="תצוגת כרטיסים">
                <Grid2X2 size={16} />
              </button>
            </div>
          </div>
        </div>
        {search || categoryFilter !== "all" || statusFilter !== "all" ? (
          <div className="mt-2 flex items-center gap-2 px-1 text-xs text-slate-400">
            <span>נמצאו {filtered.length} תוצאות</span>
            <button type="button" onClick={() => { setSearch(""); setCategoryFilter("all"); setStatusFilter("all"); }} className="font-bold text-indigo-600 hover:underline">נקה סינון</button>
          </div>
        ) : null}
      </div>

      {isLoading && <div className="rounded-2xl border bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><TableSkeleton rows={6} cols={7} /></div>}
      {isError && <ErrorState description="טעינת הקטלוג נכשלה." onRetry={() => refetch()} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          icon={Package}
          title={products && products.length > 0 ? "לא נמצאו מוצרים התואמים לסינון" : "אין מוצרים עדיין"}
          description={products && products.length > 0 ? "נסה חיפוש או סינון אחר." : canManage ? "צור את המוצר הראשון שלך כדי להתחיל ליצור הזמנות." : undefined}
          actionLabel={canManage && (!products || products.length === 0) ? "מוצר חדש" : undefined}
          onAction={openCreateModal}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && viewMode === "list" && (
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell></TableHeaderCell>
              <TableHeaderCell>מק"ט</TableHeaderCell>
              <TableHeaderCell>שם</TableHeaderCell>
              <TableHeaderCell>קטגוריה</TableHeaderCell>
              <TableHeaderCell>ספק</TableHeaderCell>
              <TableHeaderCell>מחיר</TableHeaderCell>
              <TableHeaderCell>מלאי</TableHeaderCell>
              <TableHeaderCell>סטטוס</TableHeaderCell>
              {canManage && <TableHeaderCell>פעולות</TableHeaderCell>}
            </tr>
          </TableHead>
          <TableBody>
            {filtered.map((product) => (
              <TableRow key={product.id}>
                <TableCell>
                  {product.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={product.image_url} alt={product.name} className="h-9 w-9 rounded-lg object-cover bg-slate-100" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                  ) : (
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-300 dark:bg-slate-800"><ImageOff size={14} /></div>
                  )}
                </TableCell>
                <TableCell className="text-slate-500">{product.sku || "—"}</TableCell>
                <TableCell className="font-medium text-slate-900 dark:text-white">{renderInlineCell(product, "name", product.name)}</TableCell>
                <TableCell className="text-slate-500">{product.category || "—"}</TableCell>
                <TableCell>{supplierName(product.supplier_id)}</TableCell>
                <TableCell>{renderInlineCell(product, "current_price", <><span className="font-semibold">{product.currency} {product.current_price.toLocaleString()}</span>{product.unit && <span className="text-slate-400"> / {product.unit}</span>}</>)}</TableCell>
                <TableCell>{canManage ? renderInlineCell(product, "current_stock", renderStock(product, true)) : renderStock(product)}</TableCell>
                <TableCell><ActiveBadge active={product.active} /></TableCell>
                {canManage && (
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <button type="button" onClick={() => openEditModal(product)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800" aria-label="עריכת מוצר" title="עריכה מלאה"><Pencil size={16} /></button>
                      <button type="button" onClick={() => { setEditingProduct(product); toggleActive.mutate(!product.active); }} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800" aria-label={product.active ? "השבתת מוצר" : "הפעלת מוצר"}><Power size={16} /></button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {!isLoading && !isError && filtered.length > 0 && viewMode === "grid" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {filtered.map((product) => {
            const low = isLowStock(product);
            return (
              <article key={product.id} className="group overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg dark:border-slate-800 dark:bg-slate-900">
                <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-950">
                  {product.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={product.image_url} alt={product.name} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-slate-300 shadow-sm dark:bg-slate-800"><ImageOff size={28} /></div>
                  )}
                  <div className="absolute right-3 top-3"><ActiveBadge active={product.active} /></div>
                  {low && <div className="absolute left-3 top-3 rounded-full bg-red-500 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm">מלאי נמוך</div>}
                </div>
                <div className="space-y-4 p-4">
                  <div className="min-w-0">
                    <p className="truncate text-lg font-extrabold text-slate-900 dark:text-white">{product.name}</p>
                    <div className="mt-1 flex flex-wrap gap-x-2 text-xs text-slate-400">
                      {product.sku && <span>מק"ט {product.sku}</span>}
                      {product.category && <span>• {product.category}</span>}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/70">
                      <p className="text-[11px] font-bold text-slate-400">מחיר</p>
                      <p className="mt-1 font-extrabold text-slate-900 dark:text-white">{product.currency} {product.current_price.toLocaleString()}</p>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/70">
                      <p className="text-[11px] font-bold text-slate-400">מלאי</p>
                      <div className="mt-1">{renderStock(product, true)}</div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs dark:border-slate-800">
                    <span className="truncate text-slate-400">{supplierName(product.supplier_id)}</span>
                    {canManage && <button type="button" onClick={() => openEditModal(product)} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 font-bold text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40"><Pencil size={13} /> עריכה</button>}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingProduct ? "עריכת מוצר" : "מוצר חדש"}>
        <div className="space-y-3">
          <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">ספק</label><Select value={form.supplier_id} onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}><option value="">בחר ספק...</option>{suppliers?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">שם</label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מק"ט</label><Input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} /></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מחיר</label><Input type="number" min={0} step="0.01" value={form.current_price} onChange={(e) => setForm((f) => ({ ...f, current_price: e.target.value }))} /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">קטגוריה</label><Input value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} placeholder="לדוגמה: משקאות" list="catalog-categories" /><datalist id="catalog-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">יחידת מכירה</label><Input value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} placeholder="יחידה, קילו, ארגז" /></div>
          </div>
          <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">תיאור</label><textarea className={inputClass} rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} /></div>
          <button type="button" onClick={() => setShowMoreFields((v) => !v)} className="text-sm font-medium text-primary hover:underline">{showMoreFields ? "הסתר פרטים נוספים" : "פרטים נוספים (תמונה, ברקוד, מלאי...)"}</button>
          {showMoreFields && (
            <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950/60">
              <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">כתובת תמונה</label><Input value={form.image_url} onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))} placeholder="https://..." /></div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2"><div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">ברקוד</label><Input value={form.barcode} onChange={(e) => setForm((f) => ({ ...f, barcode: e.target.value }))} inputMode="numeric" /></div><div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">קוד מוצר של הספק</label><Input value={form.supplier_sku} onChange={(e) => setForm((f) => ({ ...f, supplier_sku: e.target.value }))} /></div></div>
              <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">יחידות בקרטון</label><Input type="number" min={0} value={form.units_per_carton} onChange={(e) => setForm((f) => ({ ...f, units_per_carton: e.target.value }))} /></div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מלאי קיים</label><Input type="number" min={0} value={form.current_stock} onChange={(e) => setForm((f) => ({ ...f, current_stock: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מלאי מינימום</label><Input type="number" min={0} value={form.min_stock} onChange={(e) => setForm((f) => ({ ...f, min_stock: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מלאי מומלץ</label><Input type="number" min={0} value={form.recommended_stock} onChange={(e) => setForm((f) => ({ ...f, recommended_stock: e.target.value }))} /></div></div>
            </div>
          )}
          {editingProduct && <PriceComparison productId={editingProduct.id} primarySupplierId={editingProduct.supplier_id} primarySupplierName={supplierName(editingProduct.supplier_id)} primaryPrice={editingProduct.current_price} currency={editingProduct.currency} suppliers={suppliers} canManage={canManage} />}
          {editingProduct && <p className="text-xs text-slate-400">שינוי המחיר משפיע רק על הזמנות עתידיות — הזמנות שכבר בוצעו שומרות על המחיר שבו נוצרו.</p>}
          {formError && <p className="text-sm text-red-500">{formError}</p>}
          <div className="flex gap-2 pt-2"><Button onClick={handleSubmit} disabled={isSaving}>{isSaving ? "שומר..." : editingProduct ? "שמירת שינויים" : "יצירת מוצר"}</Button><Button variant="ghost" onClick={() => setModalOpen(false)} disabled={isSaving}>ביטול</Button></div>
        </div>
      </Modal>
    </div>
  );
}
