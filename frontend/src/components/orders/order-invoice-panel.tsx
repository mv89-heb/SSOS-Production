"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Wallet } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type Payment = { id: number; amount: number; payment_date: string; reference: string | null; notes: string | null };
type Invoice = { id: number; order_id: number; approval_status: "pending_approval" | "approved_for_payment"; approved_by: number | null; approved_at: string | null; approval_note: string | null; receipt_id: number | null; invoice_number: string; invoice_date: string | null; due_date: string | null; amount: number; paid_amount: number; balance: number; currency: string; status: string; notes: string | null; attachment_filename: string | null; attachment_size: number | null; line_comparison: Array<{ order_index: number; order_item_id?: number | null; received_quantity?: number | null; received_quantity_difference?: number | null; product_name: string; ordered_quantity: number; invoiced_quantity: number; ordered_unit_price: number; invoiced_unit_price: number; quantity_difference: number; unit_price_difference: number; amount_difference: number }>; payments: Payment[] };
type InvoiceListResponse = { success: boolean; invoices: Invoice[] };
type CreditAdjustment = {
  id: number;
  invoice_id: number | null;
  reference_number: string;
  adjustment_type: "credit_note" | "price_adjustment" | "goods_return";
  adjustment_date: string;
  amount: number;
  currency: string;
  reason: string | null;
  status: "active" | "voided";
  void_reason: string | null;
};
type CreditAdjustmentListResponse = { success: boolean; credit_adjustments: CreditAdjustment[] };
const CREDIT_ADJUSTMENT_LABELS: Record<CreditAdjustment["adjustment_type"], string> = {
  credit_note: "תעודת זיכוי",
  price_adjustment: "התאמת מחיר",
  goods_return: "החזרת סחורה",
};

function todayLocal() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function OrderInvoicePanel({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(todayLocal());
  const [dueDate, setDueDate] = useState("");
  const [receiptId, setReceiptId] = useState("");
  const [invoiceNotes, setInvoiceNotes] = useState("");
  const [creditReference, setCreditReference] = useState("");
  const [creditType, setCreditType] = useState<CreditAdjustment["adjustment_type"]>("credit_note");
  const [creditDate, setCreditDate] = useState(todayLocal());
  const [creditAmount, setCreditAmount] = useState("");
  const [creditInvoiceId, setCreditInvoiceId] = useState("");
  const [creditReason, setCreditReason] = useState("");
  const [voidingCreditId, setVoidingCreditId] = useState<number | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [paymentDrafts, setPaymentDrafts] = useState<Record<number, { amount: string; date: string; reference: string }>>({});
  const [approvalNoteDrafts, setApprovalNoteDrafts] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [reconciliationDrafts, setReconciliationDrafts] = useState<Record<number, Record<number, { quantity: string; price: string }>>>({});
  const [savingReconciliationId, setSavingReconciliationId] = useState<number | null>(null);
  const query = useQuery({
    queryKey: ["order-invoices", order.id],
    queryFn: async () => (await apiClient.get<InvoiceListResponse>(`/api/orders/${order.id}/invoices`)).data.invoices,
    enabled: order.status === "sent" || order.status === "completed",
  });
  const creditQuery = useQuery({
    queryKey: ["order-credit-adjustments", order.id],
    queryFn: async () => (await apiClient.get<CreditAdjustmentListResponse>(`/api/orders/${order.id}/credit-adjustments`)).data.credit_adjustments,
    enabled: order.status === "sent" || order.status === "completed",
  });
  const invalidate = async () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["order-invoices", order.id] }),
    queryClient.invalidateQueries({ queryKey: ["order-credit-adjustments", order.id] }),
    queryClient.invalidateQueries({ queryKey: ["order", order.id] }),
  ]);
  const createInvoice = useMutation({
    mutationFn: async () => (await apiClient.post<{ success: boolean; invoice: Invoice }>(
      `/api/orders/${order.id}/invoices`,
      { invoice_number: invoiceNumber.trim(), amount: Number(invoiceAmount), invoice_date: invoiceDate || null, due_date: dueDate || null, receipt_id: receiptId ? Number(receiptId) : null, notes: invoiceNotes.trim() || null, currency: order.currency },
    )).data.invoice,
    onSuccess: async () => {
      setInvoiceNumber(""); setInvoiceAmount(""); setDueDate(""); setReceiptId(""); setInvoiceNotes("");
      setMessage("חשבונית הספק נרשמה בהצלחה.");
      await invalidate();
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "רישום החשבונית נכשל.");
    },
  });
  const createCreditAdjustment = useMutation({
    mutationFn: async () => (await apiClient.post<{ success: boolean; credit_adjustment: CreditAdjustment }>(
      `/api/orders/${order.id}/credit-adjustments`,
      {
        reference_number: creditReference.trim(),
        adjustment_type: creditType,
        adjustment_date: creditDate,
        amount: Number(creditAmount),
        invoice_id: creditInvoiceId ? Number(creditInvoiceId) : null,
        reason: creditReason.trim() || null,
        currency: creditInvoiceId
          ? (query.data ?? []).find((invoice) => invoice.id === Number(creditInvoiceId))?.currency ?? order.currency
          : order.currency,
      },
    )).data.credit_adjustment,
    onSuccess: async () => {
      setCreditReference("");
      setCreditAmount("");
      setCreditInvoiceId("");
      setCreditReason("");
      setCreditDate(todayLocal());
      setMessage("הזיכוי/ההתאמה נרשמו. סכום החשבונית והתשלומים לא שונו.");
      await invalidate();
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "רישום הזיכוי/ההתאמה נכשל.");
    },
  });
  const voidCreditAdjustment = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) =>
      (await apiClient.post<{ success: boolean; credit_adjustment: CreditAdjustment }>(
        `/api/supplier-credit-adjustments/${id}/void`,
        { reason },
      )).data.credit_adjustment,
    onSuccess: async () => {
      setVoidingCreditId(null);
      setVoidReason("");
      setMessage("רישום הזיכוי בוטל ונשמר ביומן הביקורת.");
      await invalidate();
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "ביטול הזיכוי נכשל.");
    },
  });
  const updateApproval = useMutation({
    mutationFn: async ({ invoiceId, approvalStatus, approvalNote }: { invoiceId: number; approvalStatus: "pending_approval" | "approved_for_payment"; approvalNote?: string }) =>
      (await apiClient.post<{ success: boolean; invoice: Invoice }>(
        `/api/supplier-invoices/${invoiceId}/approval`,
        { approval_status: approvalStatus, approval_note: approvalNote?.trim() || null },
      )).data.invoice,
    onSuccess: async (invoice) => {
      setMessage(invoice.approval_status === "approved_for_payment" ? "החשבונית אושרה לתשלום ונרשמה ביומן הפעולות." : "החשבונית הוחזרה לבדיקה.");
      await invalidate();
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "עדכון אישור החשבונית נכשל.");
    },
  });
  const addPayment = useMutation({
    mutationFn: async ({ invoiceId }: { invoiceId: number }) => {
      const draft = paymentDrafts[invoiceId];
      return (await apiClient.post<{ success: boolean; invoice: Invoice }>(
        `/api/supplier-invoices/${invoiceId}/payments`,
        { amount: Number(draft?.amount), payment_date: draft?.date, reference: draft?.reference?.trim() || null },
      )).data.invoice;
    },
    onSuccess: async (invoice) => {
      setPaymentDrafts((current) => ({ ...current, [invoice.id]: { amount: "", date: todayLocal(), reference: "" } }));
      setMessage("התשלום נרשם והיתרה עודכנה.");
      await invalidate();
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "רישום התשלום נכשל.");
    },
  });

  if (order.status !== "sent" && order.status !== "completed") return null;
  return (
    <Card className="border-violet-200 shadow-sm dark:border-violet-900/50">
      <CardHeader className="border-b border-violet-100 dark:border-violet-900/50">
        <CardTitle className="flex items-center gap-2 text-base font-extrabold"><FileText size={18} /> חשבוניות ספק ותשלומים</CardTitle>
        <p className="text-sm text-slate-500">רישום פנימי לצורכי בקרה. אין כאן העברת תשלום לבנק או תחליף להנהלת חשבונות.</p>
      </CardHeader>
      <CardContent className="space-y-5 pt-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm"><span className="font-bold">מספר חשבונית *</span><input value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} maxLength={120} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm"><span className="font-bold">סכום חשבונית ({order.currency}) *</span><input type="number" min="0.01" step="0.01" value={invoiceAmount} onChange={(e) => setInvoiceAmount(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm"><span className="font-bold">תאריך חשבונית</span><input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm"><span className="font-bold">מועד פירעון</span><input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm sm:col-span-2"><span className="font-bold">שיוך לקבלת סחורה (אופציונלי)</span><select value={receiptId} onChange={(e) => setReceiptId(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"><option value="">ללא קבלה משויכת</option>{(order.receipts ?? []).map((receipt) => <option key={receipt.id} value={receipt.id}>{receipt.receipt_number} · {receipt.received_at ? new Date(receipt.received_at).toLocaleDateString("he-IL") : "ללא תאריך"}</option>)}</select></label>
          <label className="space-y-1 text-sm sm:col-span-2"><span className="font-bold">הערות פנימיות</span><textarea rows={2} maxLength={5000} value={invoiceNotes} onChange={(e) => setInvoiceNotes(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" placeholder="הפרשי מחיר, מסמך חסר, שיחה עם הספק..." /></label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-slate-500">רישום ידני של נתוני החשבונית</span><Button onClick={() => { setMessage(null); createInvoice.mutate(); }} disabled={createInvoice.isPending || !invoiceNumber.trim() || !(Number(invoiceAmount) > 0)}><FileText size={15} /> {createInvoice.isPending ? "שומר..." : "רישום חשבונית"}</Button></div>
        {message && <p role="status" className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">{message}</p>}
        <section className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/40 p-4 dark:border-amber-900/60 dark:bg-amber-950/20">
          <div>
            <h3 className="font-extrabold text-sm">זיכויים והתאמות ספק</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">רישום אנליטי מקושר להזמנה ולחשבונית. הרישום אינו משנה את סכום החשבונית, יתרת התשלום, המלאי או ההזמנה. קובץ המקור אינו נשמר.</p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs font-bold"><span>מספר אסמכתת זיכוי *</span><input value={creditReference} onChange={(event) => setCreditReference(event.target.value)} maxLength={120} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
            <label className="space-y-1 text-xs font-bold"><span>סוג התאמה</span><select value={creditType} onChange={(event) => setCreditType(event.target.value as CreditAdjustment["adjustment_type"])} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="credit_note">תעודת זיכוי</option><option value="price_adjustment">התאמת מחיר</option><option value="goods_return">החזרת סחורה</option></select></label>
            <label className="space-y-1 text-xs font-bold"><span>תאריך מסמך *</span><input type="date" value={creditDate} onChange={(event) => setCreditDate(event.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
            <label className="space-y-1 text-xs font-bold"><span>סכום זיכוי ({creditInvoiceId ? (query.data ?? []).find((invoice) => invoice.id === Number(creditInvoiceId))?.currency ?? order.currency : order.currency}) *</span><input type="number" min="0.01" step="0.01" value={creditAmount} onChange={(event) => setCreditAmount(event.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
            <label className="space-y-1 text-xs font-bold sm:col-span-2"><span>שיוך לחשבונית (אופציונלי)</span><select value={creditInvoiceId} onChange={(event) => setCreditInvoiceId(event.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="">ללא חשבונית משויכת</option>{(query.data ?? []).map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {invoice.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</option>)}</select></label>
            <label className="space-y-1 text-xs font-bold sm:col-span-2"><span>סיבת הזיכוי / הערה</span><textarea rows={2} maxLength={2000} value={creditReason} onChange={(event) => setCreditReason(event.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] text-slate-500">האסמכתה חייבת להיות ייחודית אצל אותו ספק.</span>
            <Button type="button" onClick={() => createCreditAdjustment.mutate()} disabled={createCreditAdjustment.isPending || !creditReference.trim() || !(Number(creditAmount) > 0) || !creditDate}>
              {createCreditAdjustment.isPending ? "שומר..." : "רישום זיכוי / התאמה"}
            </Button>
          </div>
          {creditQuery.isLoading && <p className="text-xs text-slate-500">טוען זיכויים...</p>}
          {creditQuery.isError && <p role="alert" className="text-xs text-red-600">טעינת הזיכויים נכשלה.</p>}
          {(creditQuery.data ?? []).length === 0 && !creditQuery.isLoading && <p className="rounded-lg border border-dashed border-amber-200 p-3 text-xs text-slate-500 dark:border-amber-900">לא נרשמו זיכויים או התאמות להזמנה זו.</p>}
          {(creditQuery.data ?? []).map((adjustment) => (
            <div key={adjustment.id} className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-sm">{adjustment.reference_number} · {CREDIT_ADJUSTMENT_LABELS[adjustment.adjustment_type]}</div>
                  <div className="mt-1 text-xs text-slate-500">{adjustment.adjustment_date}{adjustment.invoice_id ? " · מקושר לחשבונית" : " · ללא חשבונית משויכת"}</div>
                  {adjustment.reason && <p className="mt-1 whitespace-pre-wrap text-xs text-slate-500">{adjustment.reason}</p>}
                  {adjustment.status === "voided" && <p className="mt-1 text-xs font-semibold text-red-700">בוטל: {adjustment.void_reason}</p>}
                </div>
                <div className="text-left">
                  <div className="font-extrabold">{adjustment.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {adjustment.currency}</div>
                  <div className={adjustment.status === "active" ? "text-xs font-bold text-emerald-700" : "text-xs font-bold text-red-700"}>{adjustment.status === "active" ? "פעיל במדד" : "בוטל"}</div>
                </div>
              </div>
              {adjustment.status === "active" && (
                <div className="mt-2">
                  {voidingCreditId === adjustment.id ? (
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <input value={voidReason} onChange={(event) => setVoidReason(event.target.value)} maxLength={1000} placeholder="סיבת ביטול (חובה)" className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-950" />
                      <Button type="button" variant="danger" size="sm" disabled={voidCreditAdjustment.isPending || voidReason.trim().length < 3} onClick={() => voidCreditAdjustment.mutate({ id: adjustment.id, reason: voidReason.trim() })}>אשר ביטול</Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => { setVoidingCreditId(null); setVoidReason(""); }}>סגור</Button>
                    </div>
                  ) : <Button type="button" variant="ghost" size="sm" onClick={() => { setVoidingCreditId(adjustment.id); setVoidReason(""); }}>ביטול רישום (למנהל)</Button>}
                </div>
              )}
            </div>
          ))}
        </section>
        {query.isLoading && <p className="text-sm text-slate-500">טוען חשבוניות...</p>}
        {query.isError && <p className="text-sm text-red-600">טעינת החשבוניות נכשלה. נסה לרענן את המסך.</p>}
        {(query.data ?? []).length === 0 && !query.isLoading && <p className="rounded-xl border border-dashed p-4 text-sm text-slate-500">עדיין לא נרשמו חשבוניות להזמנה זו.</p>}
        {(query.data ?? []).map((invoice) => {
          const draft = paymentDrafts[invoice.id] ?? { amount: "", date: todayLocal(), reference: "" };
          return <div key={invoice.id} className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-black">{invoice.invoice_number}</div>
                <div className="mt-1 text-xs text-slate-500">חשבונית: {invoice.invoice_date ?? "—"} · פירעון: {invoice.due_date ?? "לא הוגדר"}</div>
                {invoice.notes && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-500">{invoice.notes}</p>}
                <p className="mt-2 text-xs text-slate-500">קובץ המקור אינו נשמר במערכת. נשמרים נתוני החשבונית וההתאמות בלבד.</p>
              </div>
              <div className="text-left text-sm">
                <div>סכום: <strong>{invoice.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</strong></div>
                <div>שולם: {invoice.paid_amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</div>
                <div className={invoice.balance > 0 ? "font-black text-amber-700" : "font-black text-emerald-700"}>יתרה: {invoice.balance.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3">
              <div className="space-y-1">
                <div className="text-sm font-bold">אישור לתשלום</div>
                <div className={invoice.approval_status === "approved_for_payment" ? "text-sm font-bold text-emerald-700" : "text-sm font-bold text-amber-700"}>
                  {invoice.approval_status === "approved_for_payment" ? "מאושרת לתשלום" : "ממתינה לאישור"}
                </div>
                {invoice.approved_at && <div className="text-xs text-slate-500">אושרה בתאריך {new Date(invoice.approved_at).toLocaleString("he-IL")}</div>}
                {invoice.approval_note && <div className="text-xs text-slate-500">{invoice.approval_note}</div>}
              </div>
              <div className="flex flex-wrap gap-2">
                {invoice.approval_status !== "approved_for_payment" && <div className="mt-2 space-y-2"><label className="block text-xs text-slate-600 dark:text-slate-300">הערת אישור / נימוק חריגה (נדרש אם הכמות בחשבונית שונה מהקבלה)</label><textarea aria-label="נימוק אישור חשבונית" maxLength={2000} value={approvalNoteDrafts[invoice.id] ?? ""} onChange={(e) => setApprovalNoteDrafts((current) => ({ ...current, [invoice.id]: e.target.value }))} className="w-full rounded border px-2 py-1 text-sm dark:bg-slate-900" rows={2} /><Button disabled={updateApproval.isPending || invoice.paid_amount > 0} onClick={() => { setMessage(null); updateApproval.mutate({ invoiceId: invoice.id, approvalStatus: "approved_for_payment", approvalNote: approvalNoteDrafts[invoice.id] }); }}>{updateApproval.isPending ? "מעדכן..." : "אישור לתשלום"}</Button></div>}
                {invoice.approval_status === "approved_for_payment" && invoice.paid_amount === 0 && <Button variant="outline" disabled={updateApproval.isPending} onClick={() => { setMessage(null); updateApproval.mutate({ invoiceId: invoice.id, approvalStatus: "pending_approval" }); }}>החזרה לבדיקה</Button>}
              </div>
            </div>
            {invoice.balance > 0 && invoice.approval_status === "approved_for_payment" && <div className="grid grid-cols-1 gap-2 sm:grid-cols-4"><input aria-label="סכום תשלום" type="number" min="0.01" max={invoice.balance} step="0.01" placeholder="סכום תשלום" value={draft.amount} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, amount: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><input aria-label="תאריך תשלום" type="date" value={draft.date} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, date: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><input aria-label="אסמכתא לתשלום" placeholder="אסמכתא / מספר העברה" value={draft.reference} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, reference: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><Button onClick={() => { setMessage(null); addPayment.mutate({ invoiceId: invoice.id }); }} disabled={addPayment.isPending || !(Number(draft.amount) > 0) || Number(draft.amount) > invoice.balance || !draft.date}><Wallet size={15} /> {addPayment.isPending ? "שומר..." : "רישום תשלום"}</Button></div>}
            {invoice.balance > 0 && invoice.approval_status !== "approved_for_payment" && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">אפשר לרשום תשלום רק לאחר אישור החשבונית לתשלום.</p>}
            <div className="space-y-2 border-t pt-3">
              <div className="font-bold text-sm">השוואת שורות החשבונית להזמנה</div>
              <p className="text-xs text-slate-500">הזן ידנית את הכמות והמחיר שמופיעים בחשבונית. המחיר והפער הכספי מושווים להזמנה; הכמות שהתקבלה מחושבת מקבלות שנרשמו סופית בלבד. אם החשבונית מקושרת לקבלה מסוימת, תוצג הכמות מאותה קבלה; אחרת יוצג הסכום מכל הקבלות הסופיות להזמנה.</p>
              <div className="overflow-x-auto"><table className="w-full min-w-[800px] text-sm"><thead><tr className="border-b text-right text-xs text-slate-500"><th className="p-2">פריט</th><th className="p-2">כמות בהזמנה</th><th className="p-2">כמות שהתקבלה</th><th className="p-2">כמות בחשבונית</th><th className="p-2">מחיר בהזמנה</th><th className="p-2">מחיר בחשבונית</th><th className="p-2">פער שווי</th></tr></thead><tbody>
                {order.items.map((item, index) => {
                  const saved = invoice.line_comparison?.find((line) => line.order_index === index);
                  const draftLine = reconciliationDrafts[invoice.id]?.[index] ?? { quantity: String(saved?.invoiced_quantity ?? item.quantity), price: String(saved?.invoiced_unit_price ?? item.unit_price) };
                  const amountDiff = (Number(draftLine.quantity) || 0) * (Number(draftLine.price) || 0) - Number(item.quantity) * Number(item.unit_price);
                  // Display the server-calculated receipt quantity saved with reconciliation.
                  // Do not infer receipt totals from the order payload, which may omit receipt rows.
                  const receivedQuantity = saved?.received_quantity ?? null;
                  const receivedDiff = receivedQuantity === null ? null : (Number(draftLine.quantity) || 0) - receivedQuantity;
                  return <tr key={index} className="border-b last:border-0"><td className="p-2"><div className="font-semibold">{item.product_name}</div><div className="text-xs text-slate-500">{item.sku || "ללא מק״ט"}</div></td><td className="p-2">{item.quantity}</td><td className="p-2"><div>{receivedQuantity === null ? "—" : receivedQuantity.toLocaleString("he-IL", { maximumFractionDigits: 3 })}</div>{receivedDiff !== null && <div className={Math.abs(receivedDiff) > 0.001 ? "text-xs font-bold text-amber-700" : "text-xs text-emerald-700"}>פער מול קבלה: {receivedDiff.toLocaleString("he-IL", { maximumFractionDigits: 3 })}</div>}</td><td className="p-2"><input aria-label={`כמות בחשבונית ${item.product_name}`} type="number" min="0" step="0.001" value={draftLine.quantity} onChange={(e) => setReconciliationDrafts((current) => ({ ...current, [invoice.id]: { ...(current[invoice.id] ?? {}), [index]: { ...draftLine, quantity: e.target.value } } }))} className="w-24 rounded border px-2 py-1 dark:bg-slate-900" /></td><td className="p-2">{Number(item.unit_price).toLocaleString("he-IL", { minimumFractionDigits: 2 })}</td><td className="p-2"><input aria-label={`מחיר בחשבונית ${item.product_name}`} type="number" min="0" step="0.01" value={draftLine.price} onChange={(e) => setReconciliationDrafts((current) => ({ ...current, [invoice.id]: { ...(current[invoice.id] ?? {}), [index]: { ...draftLine, price: e.target.value } } }))} className="w-24 rounded border px-2 py-1 dark:bg-slate-900" /></td><td className={`p-2 font-bold ${Math.abs(amountDiff) > 0.01 ? "text-amber-700" : "text-emerald-700"}`}>{amountDiff.toLocaleString("he-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {invoice.currency}</td></tr>;
                })}
              </tbody></table></div>
              {invoice.line_comparison?.length > 0 && <p className="text-xs text-slate-500">ההשוואה האחרונה נשמרה. הפער החיובי/שלילי הוא לפי סכום פריט מחושב ואינו כולל בהכרח מע״מ, הנחות או דמי משלוח.</p>}
              <div className="flex justify-end"><Button disabled={savingReconciliationId === invoice.id} onClick={async () => {
                setSavingReconciliationId(invoice.id); setMessage(null);
                try {
                  const lines = order.items.map((item, index) => {
                    const saved = invoice.line_comparison?.find((line) => line.order_index === index);
                    const draftLine = reconciliationDrafts[invoice.id]?.[index] ?? { quantity: String(saved?.invoiced_quantity ?? item.quantity), price: String(saved?.invoiced_unit_price ?? item.unit_price) };
                    return { order_index: index, invoiced_quantity: Number(draftLine.quantity), invoiced_unit_price: Number(draftLine.price) };
                  });
                  await apiClient.post(`/api/supplier-invoices/${invoice.id}/reconciliation`, { lines });
                  setMessage("השוואת שורות החשבונית נשמרה.");
                  await invalidate();
                } catch (error: unknown) {
                  const e = error as { response?: { data?: { message?: string } }; message?: string };
                  setMessage(e.response?.data?.message ?? e.message ?? "שמירת ההשוואה נכשלה.");
                } finally { setSavingReconciliationId(null); }
              }}>{savingReconciliationId === invoice.id ? "שומר..." : "שמירת השוואת שורות"}</Button></div>
            </div>{invoice.payments.length > 0 && <div className="border-t pt-2"><div className="mb-2 text-xs font-bold text-slate-500">תנועות תשלום</div>{invoice.payments.map((payment) => <div key={payment.id} className="flex flex-wrap justify-between gap-2 py-1 text-sm"><span>{payment.payment_date} · {payment.reference || "ללא אסמכתא"}</span><span>{payment.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</span></div>)}</div>}
          </div>;
        })}
      </CardContent>
    </Card>
  );
}
