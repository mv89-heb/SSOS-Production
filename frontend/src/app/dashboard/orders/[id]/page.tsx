"use client";

import { use, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, FileText, Loader2, Package, Send, ShieldCheck, Truck } from "lucide-react";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderTimeline } from "@/components/orders/order-timeline";
import { WhatsAppOrderShare } from "@/components/orders/whatsapp-order-share";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useOrder, useUpdateDraftOrder, useSubmitOrder, useApproveOrder, useRejectOrder, useMarkSentOrder, useCompleteOrder } from "@/hooks/use-orders";

const money = (currency: string, value: number) => `${currency} ${value.toLocaleString("he-IL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const orderId = Number(id);
  const { user } = useAuth();
  const { data: order, isLoading, isError, error } = useOrder(orderId);
  const [isEditingDraft, setIsEditingDraft] = useState(false);
  const [notesDraft, setNotesDraft] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);

  const updateDraft = useUpdateDraftOrder(orderId);
  const submit = useSubmitOrder(orderId);
  const approve = useApproveOrder(orderId);
  const reject = useRejectOrder(orderId);
  const markSent = useMarkSentOrder(orderId);
  const complete = useCompleteOrder(orderId);
  const isMutating = updateDraft.isPending || submit.isPending || approve.isPending || reject.isPending || markSent.isPending || complete.isPending;
  const canCreateOrEdit = permissions.canCreateOrders(user);
  const isManagerOrAdmin = permissions.canApproveOrders(user);

  if (isLoading) return <div className="flex items-center gap-2 text-sm text-slate-400"><Loader2 className="animate-spin" size={16} /> טוען הזמנה...</div>;
  if (isError) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    return <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30">{status === 404 ? "ההזמנה לא נמצאה" : "שגיאת שרת בטעינת ההזמנה"}</div>;
  }
  if (!order) return <p className="text-sm text-slate-400">ההזמנה לא נמצאה</p>;

  const startEditingDraft = () => { setNotesDraft(order.notes ?? ""); setIsEditingDraft(true); };
  const saveDraft = () => updateDraft.mutate({ notes: notesDraft }, { onSuccess: () => setIsEditingDraft(false) });
  const handleReject = () => reject.mutate(rejectReason, { onSuccess: () => { setIsRejecting(false); setRejectReason(""); } });

  return (
    <div className="min-w-0 space-y-6 pb-10 animate-in fade-in duration-500">
      <Link href="/dashboard/orders" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-500 transition hover:text-indigo-700"><ArrowLeft size={16} /> חזרה להזמנות</Link>

      <header className="rounded-3xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-5 md:p-7">
        <div className="flex min-w-0 flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">הזמנת רכש</span><OrderStatusBadge status={order.status} /></div>
            <h1 className="mt-3 break-words text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">{order.order_number}</h1>
            <p className="mt-1 text-base font-semibold text-slate-600 dark:text-slate-300">{order.supplier_name}</p>
            <p className="mt-2 text-xs text-slate-400">נוצרה {new Date(order.created_at).toLocaleString("he-IL")} · עודכנה {new Date(order.updated_at).toLocaleString("he-IL")}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[430px]">
            <MiniMetric icon={Package} label="פריטים" value={String(order.items.length)} />
            <MiniMetric icon={Truck} label="ספק" value={order.supplier_name} />
            <MiniMetric icon={FileText} label="מטבע" value={order.currency} />
            <MiniMetric icon={CheckCircle2} label="סה״כ" value={money(order.currency, order.final_total)} />
          </div>
        </div>
      </header>

      <OrderTimeline currentStatus={order.status} />

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 md:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm font-extrabold text-slate-800 dark:text-white">פעולות</span>
          {canCreateOrEdit && order.status === "draft" && !isEditingDraft && <Button variant="secondary" onClick={startEditingDraft} disabled={isMutating}>עריכת טיוטה</Button>}
          {canCreateOrEdit && order.status === "draft" && <Button onClick={() => submit.mutate()} disabled={isMutating}>{submit.isPending ? "שולח..." : "שליחה לאישור"}</Button>}
          {isManagerOrAdmin && order.status === "submitted" && !isRejecting && <><Button onClick={() => approve.mutate()} disabled={isMutating}>{approve.isPending ? "מאשר..." : "אישור הזמנה"}</Button><Button variant="danger" onClick={() => setIsRejecting(true)} disabled={isMutating}>דחייה</Button></>}
          {isManagerOrAdmin && order.status === "approved" && <Button onClick={() => markSent.mutate()} disabled={isMutating}><Send size={16} /> {markSent.isPending ? "מסמן..." : "סימון כנשלח לספק"}</Button>}
          {isManagerOrAdmin && order.status === "sent" && <Button onClick={() => complete.mutate()} disabled={isMutating}><CheckCircle2 size={16} /> {complete.isPending ? "משלים..." : "סימון כהושלמה"}</Button>}
          {isMutating && <span className="inline-flex items-center gap-1 text-xs text-slate-400"><Loader2 size={13} className="animate-spin" /> מעדכן...</span>}
        </div>
      </section>

      <WhatsAppOrderShare order={order} />

      {isRejecting && <Card className="border-red-200 dark:border-red-900/50"><CardContent className="space-y-3 pt-6"><label className="block text-sm font-bold text-slate-700 dark:text-slate-200">סיבת דחייה</label><textarea autoFocus className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 dark:border-slate-700 dark:bg-slate-900" rows={3} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="כתוב בקצרה למה ההזמנה נדחית..." /><div className="flex flex-wrap gap-2"><Button variant="danger" onClick={handleReject} disabled={isMutating || !rejectReason.trim()}>{reject.isPending ? "דוחה..." : "אישור דחייה"}</Button><Button variant="ghost" onClick={() => setIsRejecting(false)} disabled={isMutating}>ביטול</Button></div></CardContent></Card>}

      {isEditingDraft && <Card><CardHeader><CardTitle className="text-base text-slate-900 dark:text-white">עריכת טיוטה</CardTitle></CardHeader><CardContent className="space-y-3 pt-0"><textarea className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 dark:border-slate-700 dark:bg-slate-900" rows={4} value={notesDraft} onChange={(e) => setNotesDraft(e.target.value)} placeholder="הערות להזמנה..." /><div className="flex flex-wrap gap-2"><Button onClick={saveDraft} disabled={isMutating}>{updateDraft.isPending ? "שומר..." : "שמירת טיוטה"}</Button><Button variant="ghost" onClick={() => setIsEditingDraft(false)} disabled={isMutating}>ביטול</Button></div></CardContent></Card>}

      <Card className="overflow-hidden border-slate-200/80 shadow-sm dark:border-slate-800">
        <CardHeader className="border-b bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/30"><div className="flex items-center justify-between gap-3"><CardTitle className="text-base text-slate-900 dark:text-white">פריטי הזמנה</CardTitle><span className="text-xs font-bold text-slate-400">{order.items.length} פריטים</span></div></CardHeader>
        <CardContent className="pt-0">
          <div className="overflow-x-auto overscroll-x-contain"><table className="w-full min-w-[720px] text-right text-sm"><thead className="border-b text-slate-500 dark:border-slate-800"><tr>{["מק\"ט", "מוצר", "כמות", "מחיר יחידה", "סה\"כ"].map((h) => <th key={h} className="px-2 py-3 font-bold">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{order.items.map((item, idx) => <tr key={`${item.product_id}-${idx}`} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/50"><td className="px-2 py-4 text-slate-500">{item.sku || "—"}</td><td className="px-2 py-4 font-bold text-slate-900 dark:text-white">{item.product_name}</td><td className="px-2 py-4 font-semibold">{item.quantity}</td><td className="px-2 py-4">{money(order.currency, item.unit_price)}</td><td className="px-2 py-4 font-black">{money(order.currency, item.total_price)}</td></tr>)}</tbody></table></div>
          <div className="mt-5 flex min-w-0 flex-col gap-5 border-t pt-5 dark:border-slate-800 md:flex-row md:justify-between"><div className="max-w-xl">{order.notes && !isEditingDraft && <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300"><p className="mb-1 font-bold text-slate-800 dark:text-slate-100">הערות</p><p className="whitespace-pre-line">{order.notes}</p></div>}{order.snapshot_taken_at && <div className="mt-3 flex items-start gap-2 text-xs text-slate-400"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-500" /><span>תמונת המחירים והפריטים הוקפאה ב־{new Date(order.snapshot_taken_at).toLocaleString("he-IL")}. שינויים עתידיים בקטלוג לא ישנו את ההזמנה הזו.</span></div>}</div><div className="w-full max-w-sm space-y-2 text-sm"><SummaryRow label="סכום ביניים" value={money(order.currency, order.subtotal)} /><SummaryRow label="הנחה" value={`-${money(order.currency, order.discount_total)}`} /><SummaryRow label="מע״מ" value={money(order.currency, order.tax_total)} /><div className="mt-2 flex justify-between border-t pt-3 text-lg font-black text-slate-950 dark:border-slate-700 dark:text-white"><span>סה״כ לתשלום</span><span>{money(order.currency, order.final_total)}</span></div></div></div>
        </CardContent>
      </Card>
    </div>
  );
}

function MiniMetric({ icon: Icon, label, value }: { icon: typeof Package; label: string; value: string }) {
  return <div className="min-w-0 rounded-xl bg-slate-50 p-3 dark:bg-slate-800/70"><div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400"><Icon size={13} />{label}</div><p className="mt-1 truncate text-sm font-black text-slate-800 dark:text-white">{value}</p></div>;
}

function SummaryRow({ label, value }: { label: string; value: string }) { return <div className="flex justify-between text-slate-500"><span>{label}</span><span className="font-semibold text-slate-700 dark:text-slate-200">{value}</span></div>; }
