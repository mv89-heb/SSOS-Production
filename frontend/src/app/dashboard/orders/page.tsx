"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { Order } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertCircle, ArrowLeft, Bell, BookmarkPlus, CheckCircle2, Clock3, Download, FileSpreadsheet, Columns3, PackageCheck, Plus, Search, Send, ShoppingCart, Trash2, XCircle } from "lucide-react";

const STATUS_FILTERS = [
  { value: "all", label: "הכול" },
  { value: "approved", label: "אושרו" },
  { value: "cancelled", label: "בוטלו" },
  { value: "completed", label: "הושלמו" },
  { value: "draft", label: "טיוטות" },
  { value: "submitted", label: "ממתינות לאישור" },
  { value: "sent", label: "אצל הספק" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["value"];
type StatusTone = "amber" | "emerald" | "sky" | "violet" | "red";
type StatusSummaryProps = {
  label: string;
  value: number;
  icon: typeof Clock3;
  tone: StatusTone;
  active: boolean;
  onClick: () => void;
};

const TONE_CLASSES: Record<StatusTone, string> = {
  amber: "bg-amber-50 text-amber-600 dark:bg-amber-950/40",
  emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40",
  sky: "bg-sky-50 text-sky-600 dark:bg-sky-950/40",
  violet: "bg-violet-50 text-violet-600 dark:bg-violet-950/40",
  red: "bg-red-50 text-red-600 dark:bg-red-950/40",
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function formatReminder(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}


type OrderColumnKey = "order_number" | "supplier" | "status" | "department" | "project" | "planned_order_date" | "reminder" | "total" | "created_at";
const ORDER_COLUMNS: { id: OrderColumnKey; label: string }[] = [
  { id: "order_number", label: "מספר הזמנה" },
  { id: "supplier", label: "ספק" },
  { id: "status", label: "סטטוס" },
  { id: "department", label: "מחלקה" },
  { id: "project", label: "פרויקט" },
  { id: "planned_order_date", label: "תאריך מתוכנן" },
  { id: "reminder", label: "תזכורת" },
  { id: "total", label: "סה״כ" },
  { id: "created_at", label: "נוצר בתאריך" },
];
const DEFAULT_ORDER_COLUMNS: OrderColumnKey[] = [
  "order_number", "supplier", "status", "reminder", "total", "created_at",
];

type SearchableOrder = Order & { search_provenance?: { matched_fields: string[]; missing_fields: string[] } };

function renderOrderColumn(order: SearchableOrder, column: OrderColumnKey, reminderAt: string | null, reminderDue: boolean): ReactNode {
  switch (column) {
    case "order_number":
      return <>
        <Link href={`/dashboard/orders/${order.id}`} className="font-extrabold text-indigo-600 hover:text-indigo-700 hover:underline dark:text-indigo-400">{order.order_number}</Link>
        {!!order.search_provenance?.matched_fields.length && <p className="mt-1 max-w-56 text-[11px] text-indigo-600 dark:text-indigo-300">התאמה: {order.search_provenance.matched_fields.join(" · ")}</p>}
        {!!order.search_provenance?.missing_fields.length && <p className="mt-1 max-w-56 text-[11px] font-semibold text-amber-700 dark:text-amber-300">חסר: {order.search_provenance.missing_fields.join(" · ")}</p>}
      </>;
    case "supplier": return <span className="font-medium text-slate-700 dark:text-slate-200">{order.supplier_name}</span>;
    case "status": return <OrderStatusBadge status={order.status} />;
    case "department": return <span>{order.department || "—"}</span>;
    case "project": return <span>{order.project || "—"}</span>;
    case "planned_order_date": return <span>{order.planned_order_date ? formatDate(order.planned_order_date) : "—"}</span>;
    case "reminder":
      return order.reminder_state !== "complete" && reminderAt
        ? <Link href={`/dashboard/orders/${order.id}`} className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold ${reminderDue ? "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" : "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"}`}><Bell size={13} /> {reminderDue ? "דורשת טיפול" : reminderAt}</Link>
        : <span className="text-xs text-slate-400">אין תזכורת</span>;
    case "total": return <span className="font-bold text-slate-800 dark:text-slate-100">{order.currency} {order.final_total.toLocaleString("he-IL")}</span>;
    case "created_at": return <span className="text-sm text-slate-500">{formatDate(order.created_at)}</span>;
  }
}

function StatusSummary({ label, value, icon: Icon, tone, active, onClick }: StatusSummaryProps) {
  return (
    <button type="button" onClick={onClick} className={`text-right rounded-2xl border p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${active ? "border-indigo-300 ring-2 ring-indigo-100 dark:border-indigo-700 dark:ring-indigo-950" : "border-slate-200/80 dark:border-slate-800"} bg-white dark:bg-slate-900`}>
      <div className="flex items-center justify-between gap-3">
        <div><p className="text-xs font-bold text-slate-400">{label}</p><p className="mt-1 text-2xl font-extrabold text-slate-900 dark:text-white">{value}</p></div>
        <div className={`rounded-xl p-2.5 ${TONE_CLASSES[tone]}`}><Icon size={18} /></div>
      </div>
    </button>
  );
}

export default function OrdersPage() {
  const queryClient = useQueryClient();
  const { data: orders } = useQuery({ queryKey: ["orders"], queryFn: () => orderService.getOrders() });
  const { data: savedSearches = [] } = useQuery({
    queryKey: ["orders", "saved-searches"],
    queryFn: () => orderService.getSavedSearches(),
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [isExportingExcel, setIsExportingExcel] = useState(false);
  const [exportError, setExportError] = useState("");
  const [selectedSavedSearchId, setSelectedSavedSearchId] = useState("");
  const [showSaveSearch, setShowSaveSearch] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");
  const [savedSearchMessage, setSavedSearchMessage] = useState("");
  const [page, setPage] = useState(0);
  const [visibleColumns, setVisibleColumns] = useState<OrderColumnKey[]>(DEFAULT_ORDER_COLUMNS);
  const [columnsLoaded, setColumnsLoaded] = useState(false);
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [selectedOrderIds, setSelectedOrderIds] = useState<number[]>([]);
  const [showBulkConfirm, setShowBulkConfirm] = useState(false);
  const [bulkActionMessage, setBulkActionMessage] = useState("");
  const deferredSearch = useDeferredValue(search.trim());

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("ssos.orders.visible-columns.v1");
      if (stored) {
        const parsed: unknown = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          const valid = parsed.filter((value): value is OrderColumnKey =>
            ORDER_COLUMNS.some((column) => column.id === value)
          );
          if (valid.length > 0) setVisibleColumns(valid);
        }
      }
    } catch {
      // Invalid or unavailable local preferences fall back to the full default set.
    } finally {
      setColumnsLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (columnsLoaded) {
      window.localStorage.setItem("ssos.orders.visible-columns.v1", JSON.stringify(visibleColumns));
    }
  }, [columnsLoaded, visibleColumns]);

  useEffect(() => {
    setSelectedOrderIds([]);
    setShowBulkConfirm(false);
  }, [deferredSearch, status, startDate, endDate, page]);
  const pageSize = 50;
  const { data: searchResult, isLoading, isError, refetch } = useQuery({
    queryKey: ["orders", "search", deferredSearch, status, startDate, endDate, page],
    queryFn: () => orderService.searchOrders({
      q: deferredSearch || undefined,
      status: status === "all" ? undefined : status,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      limit: pageSize,
      offset: page * pageSize,
    }),
    placeholderData: (previousData) => previousData,
  });
  const createSavedSearchMutation = useMutation({
    mutationFn: (payload: { name: string; filters: { q: string; status: string; start_date: string; end_date: string } }) =>
      orderService.createSavedSearch(payload),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ["orders", "saved-searches"] });
      setSelectedSavedSearchId(String(saved.id));
      setShowSaveSearch(false);
      setSaveSearchName("");
      setSavedSearchMessage("החיפוש נשמר.");
    },
    onError: () => setSavedSearchMessage("לא ניתן לשמור את החיפוש. בדוק שהשם אינו קיים ושלא נשמרו כבר 20 חיפושים."),
  });
  const bulkMarkSentMutation = useMutation({
    mutationFn: (ids: number[]) => orderService.markOrdersSent(ids),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["orders"] });
      setSelectedOrderIds([]);
      setShowBulkConfirm(false);
      setBulkActionMessage(`עודכנו ${result.updated_count} הזמנות לסטטוס "נשלחה לספק". הפעולה נרשמה ביומן הביקורת.`);
    },
    onError: () => {
      setShowBulkConfirm(false);
      setBulkActionMessage("הפעולה לא בוצעה. ייתכן שאחת ההזמנות כבר אינה מאושרת; לא בוצע עדכון חלקי.");
    },
  });
  const deleteSavedSearchMutation = useMutation({
    mutationFn: (id: number) => orderService.deleteSavedSearch(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["orders", "saved-searches"] });
      setSelectedSavedSearchId("");
      setSavedSearchMessage("החיפוש השמור נמחק.");
    },
    onError: () => setSavedSearchMessage("מחיקת החיפוש נכשלה."),
  });
  const filteredOrders = useMemo(() => searchResult?.orders ?? [], [searchResult]);
  const selectedOrders = filteredOrders.filter((order) => selectedOrderIds.includes(order.id));
  const allPageOrdersSelected = filteredOrders.length > 0 && filteredOrders.every((order) => selectedOrderIds.includes(order.id));
  const canBulkMarkSent = selectedOrderIds.length > 0
    && selectedOrders.length === selectedOrderIds.length
    && selectedOrders.every((order) => order.status === "approved");
  const toggleOrderSelection = (orderId: number, checked: boolean) => {
    setSelectedOrderIds((current) => checked
      ? (current.includes(orderId) ? current : [...current, orderId])
      : current.filter((id) => id !== orderId));
    setBulkActionMessage("");
  };
  const togglePageSelection = (checked: boolean) => {
    setSelectedOrderIds(checked ? filteredOrders.map((order) => order.id) : []);
    setBulkActionMessage("");
  };
  const toggleColumn = (columnId: OrderColumnKey, checked: boolean) => {
    setVisibleColumns((current) => {
      if (checked) return current.includes(columnId) ? current : [...current, columnId];
      if (current.length <= 1) return current;
      return current.filter((column) => column !== columnId);
    });
  };
  const count = (value: string) => (orders ?? []).filter((order) => order.status === value).length;
  const hasFilters = Boolean(search.trim()) || status !== "all" || Boolean(startDate) || Boolean(endDate);
  const totalResults = searchResult?.pagination.total ?? 0;
  const hasPreviousPage = page > 0;
  const hasNextPage = Boolean(searchResult?.pagination.has_more);
  const changeStatus = (value: StatusFilter) => { setStatus(value); setSelectedSavedSearchId(""); setPage(0); };
  const clearFilters = () => { setSearch(""); setStartDate(""); setEndDate(""); setSelectedSavedSearchId(""); changeStatus("all"); };
  const applySavedSearch = (value: string) => {
    setSelectedSavedSearchId(value);
    const saved = savedSearches.find((item) => item.id === Number(value));
    if (!saved) return;
    setSearch(saved.filters.q || "");
    setStatus((saved.filters.status || "all") as StatusFilter);
    setStartDate(saved.filters.start_date || "");
    setEndDate(saved.filters.end_date || "");
    setPage(0);
  };
  const saveCurrentSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavedSearchMessage("");
    createSavedSearchMutation.mutate({
      name: saveSearchName,
      filters: {
        q: search.trim(),
        status,
        start_date: startDate,
        end_date: endDate,
      },
    });
  };
  const handleExport = async (format: "csv" | "xlsx") => {
    if (format === "csv") setIsExporting(true);
    else setIsExportingExcel(true);
    setExportError("");
    try {
      const blob = await orderService.exportOrders({
        q: search.trim() || undefined,
        status: status === "all" ? undefined : status,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }, format);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `orders-${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch {
      setExportError("הייצוא נכשל. אם יש יותר מ־5,000 הזמנות, צמצם את החיפוש או את טווח התאריכים.");
    } finally {
      if (format === "csv") setIsExporting(false);
      else setIsExportingExcel(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">הזמנות רכש</h1>
            {orders && <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">{orders.length} הזמנות</span>}
          </div>
          <p className="mt-1 text-sm text-slate-500">מרכז העבודה לניהול, מעקב ואישור הזמנות.</p>
        </div>
        <Link href="/dashboard/orders/new"><Button className="shadow-sm"><Plus size={16} /> הזמנה חדשה</Button></Link>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <StatusSummary label="ממתינות לאישור" value={count("submitted")} icon={Clock3} tone="amber" active={status === "submitted"} onClick={() => changeStatus("submitted")} />
        <StatusSummary label="אושרו" value={count("approved")} icon={CheckCircle2} tone="emerald" active={status === "approved"} onClick={() => changeStatus("approved")} />
        <StatusSummary label="אצל הספק" value={count("sent")} icon={Send} tone="sky" active={status === "sent"} onClick={() => changeStatus("sent")} />
        <StatusSummary label="הושלמו" value={count("completed")} icon={PackageCheck} tone="violet" active={status === "completed"} onClick={() => changeStatus("completed")} />
        <StatusSummary label="בוטלו" value={count("cancelled")} icon={XCircle} tone="red" active={status === "cancelled"} onClick={() => changeStatus("cancelled")} />
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-100 p-3 dark:border-slate-800">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input value={search} onChange={(e) => { setSearch(e.target.value); setSelectedSavedSearchId(""); setPage(0); }} placeholder="חיפוש חופשי: הזמנה, ספק, מוצר, מק״ט, הערות, מחלקה או פרויקט..." className="h-10 pr-9" />
            </div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" variant="secondary" onClick={() => handleExport("csv")} disabled={isExporting || isExportingExcel || totalResults === 0}>
                <Download size={15} /> {isExporting ? "מייצא..." : "CSV"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => handleExport("xlsx")} disabled={isExporting || isExportingExcel || totalResults === 0}>
                <FileSpreadsheet size={15} /> {isExportingExcel ? "מייצא..." : "Excel"}
              </Button>
            </div>
            <Button type="button" variant="secondary" onClick={() => setShowColumnSettings((value) => !value)} className="shrink-0">
              <Columns3 size={15} /> עמודות
            </Button>
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {STATUS_FILTERS.map((filter) => <button key={filter.value} type="button" onClick={() => changeStatus(filter.value)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-bold transition ${status === filter.value ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-50 text-slate-500 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300"}`}>{filter.label}</button>)}
            </div>
          </div>
          {showColumnSettings && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-xs font-extrabold text-slate-600 dark:text-slate-200">עמודות בטבלת ההזמנות</p>
                <button type="button" onClick={() => setVisibleColumns(DEFAULT_ORDER_COLUMNS)} className="text-xs font-bold text-indigo-600 hover:underline dark:text-indigo-300">איפוס לברירת מחדל</button>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {ORDER_COLUMNS.map((column) => (
                  <label key={column.id} className="inline-flex min-h-8 items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                    <input type="checkbox" checked={visibleColumns.includes(column.id)} onChange={(event) => toggleColumn(column.id, event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    {column.label}
                  </label>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-400">הבחירה נשמרת בדפדפן הזה. לפחות עמודה אחת חייבת להישאר מוצגת.</p>
            </div>
          )}
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:max-w-md">
            <label className="flex flex-col gap-1 text-xs font-bold text-slate-500">
              מתאריך
              <input type="date" value={startDate} max={endDate || undefined} onChange={(event) => { setStartDate(event.target.value); setSelectedSavedSearchId(""); setPage(0); }} className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:ring-indigo-950" />
            </label>
            <label className="flex flex-col gap-1 text-xs font-bold text-slate-500">
              עד תאריך
              <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setSelectedSavedSearchId(""); setPage(0); }} className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:ring-indigo-950" />
            </label>
          </div>
          <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 dark:border-slate-800 sm:flex-row sm:items-end">
            <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs font-bold text-slate-500">
              חיפושים שמורים ({savedSearches.length}/20)
              <select value={selectedSavedSearchId} onChange={(event) => applySavedSearch(event.target.value)} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                <option value="">בחירת חיפוש שמור...</option>
                {savedSearches.map((saved) => <option key={saved.id} value={saved.id}>{saved.name}</option>)}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={() => { setShowSaveSearch((value) => !value); setSavedSearchMessage(""); }}>
                <BookmarkPlus size={15} /> שמור חיפוש נוכחי
              </Button>
              {selectedSavedSearchId && <Button type="button" variant="danger" onClick={() => deleteSavedSearchMutation.mutate(Number(selectedSavedSearchId))} disabled={deleteSavedSearchMutation.isPending}>
                <Trash2 size={15} /> מחק שמור
              </Button>}
            </div>
          </div>
          {showSaveSearch && (
            <form onSubmit={saveCurrentSearch} className="mt-2 flex flex-col gap-2 rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60 sm:flex-row sm:items-end">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs font-bold text-slate-500">
                שם לחיפוש
                <input required maxLength={80} value={saveSearchName} onChange={(event) => setSaveSearchName(event.target.value)} placeholder="לדוגמה: הזמנות חלב לשבת" className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" />
              </label>
              <div className="flex gap-2">
                <Button type="submit" disabled={createSavedSearchMutation.isPending || savedSearches.length >= 20}>{createSavedSearchMutation.isPending ? "שומר..." : "שמור"}</Button>
                <Button type="button" variant="ghost" onClick={() => setShowSaveSearch(false)}>ביטול</Button>
              </div>
            </form>
          )}
          {savedSearchMessage && <p role="status" className="mt-2 px-1 text-xs font-semibold text-slate-600 dark:text-slate-300">{savedSearchMessage}</p>}
          {selectedOrderIds.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 rounded-xl border border-indigo-200 bg-indigo-50/70 p-3 dark:border-indigo-900 dark:bg-indigo-950/30 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-xs font-bold text-indigo-900 dark:text-indigo-200">
                נבחרו {selectedOrderIds.length} הזמנות בעמוד הנוכחי
                {!canBulkMarkSent && <p className="mt-1 font-medium text-amber-700 dark:text-amber-300">כדי לסמן כנשלח, כל ההזמנות שנבחרו חייבות להיות במצב "אושרה".</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => setShowBulkConfirm(true)} disabled={!canBulkMarkSent || bulkMarkSentMutation.isPending}>
                  <Send size={15} /> סמן כנשלח לספק
                </Button>
                <Button type="button" variant="ghost" onClick={() => setSelectedOrderIds([])}>נקה בחירה</Button>
              </div>
            </div>
          )}
          {bulkActionMessage && <p role="status" className="mt-2 px-1 text-xs font-semibold text-slate-600 dark:text-slate-300">{bulkActionMessage}</p>}
          {searchResult?.search_context && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/80 p-3 text-xs dark:border-slate-800 dark:bg-slate-900/50">
              <p className="font-bold text-slate-600 dark:text-slate-300">שדות שנבדקים בחיפוש: <span className="font-medium">{searchResult.search_context.searched_fields.join(" · ")}</span></p>
              {searchResult.search_context.active_filters.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="font-bold text-slate-500">סינון פעיל:</span>
                  {searchResult.search_context.active_filters.map((filter) => <span key={filter.key} className="rounded-full bg-white px-2 py-1 font-semibold text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700">{filter.label}: {filter.value}</span>)}
                </div>
              )}
              {searchResult.search_context.data_quality.incomplete_count > 0 && (
                <p role="status" className="mt-2 flex items-start gap-1.5 font-semibold text-amber-700 dark:text-amber-300">
                  <AlertCircle size={14} className="mt-0.5 shrink-0" />
                  נמצאו {searchResult.search_context.data_quality.incomplete_count} הזמנות בעמוד הנוכחי עם שדות חובה חסרים. מומלץ לפתוח אותן ולבדוק את פרטי המקור.
                </p>
              )}
            </div>
          )}
          {hasFilters && <div className="mt-2 flex items-center justify-between px-1 text-xs"><span className="text-slate-400">נמצאו {totalResults.toLocaleString("he-IL")} הזמנות</span><button type="button" onClick={clearFilters} className="font-bold text-indigo-600 hover:underline">נקה סינון</button></div>}
          {exportError && <p role="alert" className="mt-2 px-1 text-xs font-semibold text-red-600">{exportError}</p>}
        </div>

        {isError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-12 text-center"><div className="rounded-2xl bg-red-50 p-3 text-red-500 dark:bg-red-950/30"><AlertCircle size={28} /></div><p className="font-bold text-slate-800 dark:text-white">לא הצלחנו לטעון את ההזמנות</p><p className="text-sm text-slate-500">בדוק את החיבור ונסה שוב.</p><Button variant="secondary" onClick={() => refetch()}>נסה שוב</Button></div>
        ) : isLoading ? (
          <div className="space-y-3 p-4">{[1,2,3,4,5].map((row) => <div key={row} className="h-16 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}</div>
        ) : filteredOrders.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-14 text-center"><div className="mb-4 rounded-2xl bg-slate-100 p-4 text-slate-400 dark:bg-slate-800"><ShoppingCart size={28} /></div><h2 className="font-bold text-slate-800 dark:text-white">{hasFilters ? "לא נמצאו הזמנות תואמות" : "אין הזמנות עדיין"}</h2><p className="mt-1 text-sm text-slate-500">{hasFilters ? "נסה לשנות את החיפוש או הסינון." : "צור את ההזמנה הראשונה כדי להתחיל."}</p>{hasFilters ? <Button variant="secondary" className="mt-4" onClick={clearFilters}>נקה סינון</Button> : <Link href="/dashboard/orders/new" className="mt-4"><Button><Plus size={16} /> הזמנה חדשה</Button></Link>}</div>
        ) : (
          <>
            <div className="grid gap-3 p-3 md:hidden">
              {filteredOrders.map((order) => {
                const reminderAt = formatReminder(order.next_reminder_at);
                const reminderDue = !!order.next_reminder_at && new Date(order.next_reminder_at).getTime() <= Date.now() && order.reminder_state !== "complete";
                return (
                  <article key={order.id} className="min-w-0 rounded-xl border border-slate-200 p-4 shadow-sm dark:border-slate-800">
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-2">
                        <input type="checkbox" aria-label={`בחירת הזמנה ${order.order_number}`} checked={selectedOrderIds.includes(order.id)} onChange={(event) => toggleOrderSelection(order.id, event.target.checked)} className="mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                        <div className="min-w-0">
                          <Link href={`/dashboard/orders/${order.id}`} className="break-words font-extrabold text-indigo-600 hover:underline dark:text-indigo-400">{order.order_number}</Link>
                        <p className="mt-1 break-words text-sm font-semibold text-slate-700 dark:text-slate-200">{order.supplier_name}</p>
                        {!!order.search_provenance?.matched_fields.length && <p className="mt-1 break-words text-[11px] text-indigo-600 dark:text-indigo-300">התאמה לפי: {order.search_provenance.matched_fields.join(" · ")}</p>}
                          {!!order.search_provenance?.missing_fields.length && <p className="mt-1 flex items-start gap-1 break-words text-[11px] font-semibold text-amber-700 dark:text-amber-300"><AlertCircle size={12} className="mt-0.5 shrink-0" /> מידע חסר: {order.search_provenance.missing_fields.join(" · ")}</p>}
                        </div>
                      </div>
                      <div className="shrink-0"><OrderStatusBadge status={order.status} /></div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
                      <div className="min-w-0"><p className="text-xs text-slate-500">סה״כ</p><p className="mt-1 break-words font-extrabold text-slate-900 dark:text-white">{order.currency} {order.final_total.toLocaleString("he-IL")}</p></div>
                      <div className="min-w-0"><p className="text-xs text-slate-500">נוצר בתאריך</p><p className="mt-1 text-slate-700 dark:text-slate-200">{formatDate(order.created_at)}</p></div>
                      <div className="col-span-2 min-w-0"><p className="text-xs text-slate-500">תזכורת</p>{order.reminder_state !== "complete" && reminderAt ? <p className={`mt-1 break-words text-xs font-bold ${reminderDue ? "text-amber-700 dark:text-amber-300" : "text-indigo-700 dark:text-indigo-300"}`}>{reminderDue ? "דורשת טיפול" : reminderAt}</p> : <p className="mt-1 text-xs text-slate-400">אין תזכורת</p>}</div>
                    </div>
                    <Link href={`/dashboard/orders/${order.id}`} className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-sm font-bold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-950/70">פתיחת הזמנה <ArrowLeft size={15} /></Link>
                  </article>
                );
              })}
            </div>
            <div dir="rtl" className="hidden w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain md:block">
              <table dir="rtl" className="w-max min-w-[950px] text-right text-sm">
                <thead className="border-b border-slate-100 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-950/40">
                  <tr>
                    <th className="px-4 py-3">
                      <input type="checkbox" aria-label="בחירת כל ההזמנות בעמוד" checked={allPageOrdersSelected} onChange={(event) => togglePageSelection(event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    </th>
                    {visibleColumns.map((column) => <th key={column} className="whitespace-nowrap px-5 py-3 text-xs font-extrabold text-slate-500">{ORDER_COLUMNS.find((item) => item.id === column)?.label}</th>)}
                    <th className="px-5 py-3 text-xs font-extrabold text-slate-500">פעולות</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredOrders.map((order) => {
                    const reminderAt = formatReminder(order.next_reminder_at);
                    const reminderDue = !!order.next_reminder_at && new Date(order.next_reminder_at).getTime() <= Date.now() && order.reminder_state !== "complete";
                    return (
                      <tr key={order.id} className="group transition-colors hover:bg-indigo-50/40 dark:hover:bg-slate-800/60">
                        <td className="px-4 py-4">
                          <input type="checkbox" aria-label={`בחירת הזמנה ${order.order_number}`} checked={selectedOrderIds.includes(order.id)} onChange={(event) => toggleOrderSelection(order.id, event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                        </td>
                        {visibleColumns.map((column) => (
                          <td key={column} className="max-w-64 px-5 py-4 align-top">
                            {renderOrderColumn(order, column, reminderAt, reminderDue)}
                          </td>
                        ))}
                        <td className="px-5 py-4">
                          <Link href={`/dashboard/orders/${order.id}`} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-500 opacity-70 transition hover:bg-white hover:text-indigo-600 hover:opacity-100 dark:hover:bg-slate-900">פרטים <ArrowLeft size={13} /></Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {searchResult && (
              <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-sm dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-slate-500">
                  מציג {totalResults === 0 ? 0 : page * pageSize + 1}–{Math.min((page + 1) * pageSize, totalResults)} מתוך {totalResults.toLocaleString("he-IL")} הזמנות
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" disabled={!hasPreviousPage} onClick={() => setPage((current) => Math.max(0, current - 1))}>הקודם</Button>
                  <span className="min-w-16 text-center text-xs font-bold text-slate-500">עמוד {page + 1}</span>
                  <Button variant="secondary" disabled={!hasNextPage} onClick={() => setPage((current) => current + 1)}>הבא</Button>
                </div>
              </div>
            )}
          </>
        )}
      </section>
      {showBulkConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onClick={(event) => { if (event.target === event.currentTarget) setShowBulkConfirm(false); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="bulk-send-title" className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
            <h2 id="bulk-send-title" className="text-lg font-extrabold text-slate-900 dark:text-white">אישור סימון הזמנות כנשלחו</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">הפעולה תעביר את {selectedOrders.length} ההזמנות הבאות ממצב "אושרה" למצב "נשלחה לספק". כל ההזמנות יעודכנו יחד או שאף אחת לא תעודכן.</p>
            <ul className="mt-3 max-h-48 space-y-2 overflow-y-auto rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/70">
              {selectedOrders.map((order) => <li key={order.id} className="flex justify-between gap-3"><span className="font-bold">{order.order_number}</span><span className="truncate text-slate-500">{order.supplier_name}</span></li>)}
            </ul>
            <p className="mt-3 text-xs text-slate-500">לכל הזמנה יירשם אירוע נפרד ביומן הביקורת. לא נשלחת הודעה לספק מתוך פעולה זו.</p>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setShowBulkConfirm(false)} disabled={bulkMarkSentMutation.isPending}>ביטול</Button>
              <Button type="button" onClick={() => bulkMarkSentMutation.mutate(selectedOrderIds)} disabled={bulkMarkSentMutation.isPending || !canBulkMarkSent}>
                {bulkMarkSentMutation.isPending ? "מעדכן..." : "אשר וסמן כנשלח"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
