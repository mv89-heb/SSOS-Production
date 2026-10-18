"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Wallet } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type Payment = { id: number; amount: number; payment_date: string; reference: string | null; notes: string | null };
type Invoice = { id: number; order_id: number; receipt_id: number | null; invoice_number: string; invoice_date: string | null; due_date: string | null; amount: number; paid_amount: number; balance: number; currency: string; status: string; notes: string | null; payments: Payment[] };
type InvoiceListResponse = { success: boolean; invoices: Invoice[] };

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
  const [paymentDrafts, setPaymentDrafts] = useState<Record<number, { amount: string; date: string; reference: string }>>({});
  const [message, setMessage] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["order-invoices", order.id],
    queryFn: async () => (await apiClient.get<InvoiceListResponse>(`/api/orders/${order.id}/invoices`)).data.invoices,
    enabled: order.status === "sent" || order.status === "completed",
  });
  const invalidate = async () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["order-invoices", order.id] }),
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
        {query.isLoading && <p className="text-sm text-slate-500">טוען חשבוניות...</p>}
        {query.isError && <p className="text-sm text-red-600">טעינת החשבוניות נכשלה. נסה לרענן את המסך.</p>}
        {(query.data ?? []).length === 0 && !query.isLoading && <p className="rounded-xl border border-dashed p-4 text-sm text-slate-500">עדיין לא נרשמו חשבוניות להזמנה זו.</p>}
        {(query.data ?? []).map((invoice) => {
          const draft = paymentDrafts[invoice.id] ?? { amount: "", date: todayLocal(), reference: "" };
          return <div key={invoice.id} className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="font-black">{invoice.invoice_number}</div><div className="mt-1 text-xs text-slate-500">חשבונית: {invoice.invoice_date ?? "—"} · פירעון: {invoice.due_date ?? "לא הוגדר"}</div>{invoice.notes && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-500">{invoice.notes}</p>}</div><div className="text-left text-sm"><div>סכום: <strong>{invoice.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</strong></div><div>שולם: {invoice.paid_amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</div><div className={invoice.balance > 0 ? "font-black text-amber-700" : "font-black text-emerald-700"}>יתרה: {invoice.balance.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</div></div></div>
            {invoice.balance > 0 && <div className="grid grid-cols-1 gap-2 sm:grid-cols-4"><input aria-label="סכום תשלום" type="number" min="0.01" max={invoice.balance} step="0.01" placeholder="סכום תשלום" value={draft.amount} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, amount: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><input aria-label="תאריך תשלום" type="date" value={draft.date} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, date: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><input aria-label="אסמכתא לתשלום" placeholder="אסמכתא / מספר העברה" value={draft.reference} onChange={(e) => setPaymentDrafts((current) => ({ ...current, [invoice.id]: { ...draft, reference: e.target.value } }))} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /><Button onClick={() => { setMessage(null); addPayment.mutate({ invoiceId: invoice.id }); }} disabled={addPayment.isPending || !(Number(draft.amount) > 0) || Number(draft.amount) > invoice.balance || !draft.date}><Wallet size={15} /> {addPayment.isPending ? "שומר..." : "רישום תשלום"}</Button></div>}
            {invoice.payments.length > 0 && <div className="border-t pt-2"><div className="mb-2 text-xs font-bold text-slate-500">תנועות תשלום</div>{invoice.payments.map((payment) => <div key={payment.id} className="flex flex-wrap justify-between gap-2 py-1 text-sm"><span>{payment.payment_date} · {payment.reference || "ללא אסמכתא"}</span><span>{payment.amount.toLocaleString("he-IL", { minimumFractionDigits: 2 })} {invoice.currency}</span></div>)}</div>}
          </div>;
        })}
      </CardContent>
    </Card>
  );
}
