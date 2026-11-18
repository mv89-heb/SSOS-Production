"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSearch, PackageCheck, RefreshCw } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type ReceiptItem = { id: number; receipt_id: number; order_item_id: number; quantity: number; damaged_quantity?: number; accepted_quantity?: number; damage_notes?: string | null };
type Receipt = { id: number; receipt_number: string; status: string; received_at: string | null; notes: string | null; items: ReceiptItem[] };
type ReceiptResponse = { success: boolean; receipts: Receipt[] };
type ReceiptCreateResponse = { success: boolean; receipt: Receipt };

export function OrderReceivingPanel({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const lines = order.order_items ?? [];
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [damagedQuantities, setDamagedQuantities] = useState<Record<number, string>>({});
  const [damageNotes, setDamageNotes] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const receiptsQuery = useQuery({
    queryKey: ["order-receipts", order.id],
    queryFn: async () => {
      const { data } = await apiClient.get<ReceiptResponse>(`/api/orders/${order.id}/receipts`);
      return data.receipts;
    },
    enabled: order.status === "sent",
  });
  const receiptTotalsByLine = useMemo(() => {
    const totals = new Map<number, { physical: number; damaged: number; accepted: number }>();
    (receiptsQuery.data ?? []).forEach((receipt) => {
      if (receipt.status !== "posted") return;
      receipt.items.forEach((item) => {
        const current = totals.get(item.order_item_id) ?? { physical: 0, damaged: 0, accepted: 0 };
        const damaged = Number(item.damaged_quantity ?? 0);
        current.physical += item.quantity;
        current.damaged += damaged;
        current.accepted += Number(item.accepted_quantity ?? (item.quantity - damaged));
        totals.set(item.order_item_id, current);
      });
    });
    return totals;
  }, [receiptsQuery.data]);
  const createReceipt = useMutation({
    mutationFn: async () => {
      const items: Array<{ order_item_id: number; quantity: number; damaged_quantity: number; damage_notes?: string }> = [];
      for (const line of lines) {
        const rawQuantity = quantities[line.id]?.trim();
        const rawDamaged = damagedQuantities[line.id]?.trim();
        if (!rawQuantity && !rawDamaged) continue;
        const quantity = Number(rawQuantity || 0);
        const damaged = Number(rawDamaged || 0);
        if (!Number.isFinite(quantity) || !Number.isInteger(quantity) || quantity < 0 ||
            !Number.isFinite(damaged) || !Number.isInteger(damaged) || damaged < 0 || damaged > quantity) {
          throw new Error("יש להזין כמויות שלמות; הכמות הפגומה אינה יכולה לעלות על הכמות שהגיעה");
        }
        if (quantity === 0) continue;
        const label = line.product_snapshot?.name ?? `פריט ${line.id}`;
        const reason = damageNotes[line.id]?.trim() || "";
        if (damaged > 0 && !reason) throw new Error(`יש לציין סיבת פגם עבור ${label}`);
        const ordered = Number(line.quantity);
        const received = receiptTotalsByLine.get(line.id)?.accepted ?? 0;
        const remaining = Math.max(0, ordered - received);
        const accepted = quantity - damaged;
        if (accepted > remaining) {
          throw new Error(`הכמות התקינה עבור ${label} גדולה מהיתרה להזמנה (${remaining})`);
        }
        items.push({ order_item_id: line.id, quantity, damaged_quantity: damaged, damage_notes: reason || undefined });
      }
      if (!items.length) throw new Error("יש להזין כמות שהתקבלה לפחות בפריט אחד");
      const { data } = await apiClient.post<ReceiptCreateResponse>(
        `/api/orders/${order.id}/receipts`,
        { items, notes: notes.trim() || null },
        { headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      return data.receipt;
    },
    onSuccess: async (receipt) => {
      setMessage(`הקבלה ${receipt.receipt_number} נשמרה. הכמות התקינה נוספה למלאי והכמות הפגומה הוחרגה.`);
      setQuantities({});
      setDamagedQuantities({});
      setDamageNotes({});
      setNotes("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order-receipts", order.id] }),
        queryClient.invalidateQueries({ queryKey: ["order", order.id] }),
        queryClient.invalidateQueries({ queryKey: ["inventory"] }),
      ]);
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "שמירת הקבלה נכשלה");
    },
  });

  if (order.status !== "sent") return null;
  return (
    <Card className="border-emerald-200 shadow-sm dark:border-emerald-900/50">
      <CardHeader className="border-b border-emerald-100 dark:border-emerald-900/50">
        <CardTitle className="flex items-center gap-2 text-base font-extrabold"><PackageCheck size={18} /> קבלת סחורה בפועל</CardTitle>
        <p className="text-sm text-slate-500">רשום כמות פיזית שהגיעה וכמות פגומה בנפרד. רק הכמות התקינה תתווסף למלאי; פגום מחייב סיבת פגם ונשאר פתוח להשלמה.</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-200 bg-indigo-50/70 p-4 dark:border-indigo-900/60 dark:bg-indigo-950/20">
          <div className="min-w-0">
            <h3 className="flex items-center gap-2 text-sm font-bold text-indigo-950 dark:text-indigo-100"><FileSearch size={16} /> סריקת תעודת משלוח והשוואה להזמנה</h3>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">העלה מסמך אחד או כמה במסך Gemini, זהה ספק ופריטים, השווה להזמנה זו ואשר קבלה רק לאחר בדיקה.</p>
          </div>
          <a href={`/dashboard/document-intelligence?orderId=${order.id}`} className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-700">
            <FileSearch size={15} /> פתיחת ניתוח מסמכים להזמנה
          </a>
        </section>
        {receiptsQuery.isLoading ? <p className="text-sm text-slate-500">טוען קבלות קודמות...</p> : null}
        {receiptsQuery.isError ? <div className="flex items-center justify-between gap-2 text-sm text-red-600"><span>לא ניתן לטעון קבלות קודמות.</span><Button variant="secondary" onClick={() => receiptsQuery.refetch()}><RefreshCw size={14} /> נסה שוב</Button></div> : null}
        {lines.length === 0 ? <p className="text-sm text-amber-700">לא נמצאו שורות רכש תפעוליות להזמנה זו, ולכן לא ניתן לרשום קבלה דרך המסך.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-right text-sm"><thead><tr className="border-b text-slate-500">
            <th className="py-2">פריט</th><th className="py-2">הוזמן</th><th className="py-2">הגיע פיזית</th><th className="py-2">פגום עד כה</th><th className="py-2">תקין שהתקבל</th><th className="py-2">יתרה תקינה</th><th className="py-2">הגיע כעת</th><th className="py-2">פגום כעת</th><th className="py-2">תקין כעת</th><th className="py-2">חוסר אחרי הקבלה</th><th className="py-2">סיבת פגם</th>
          </tr></thead><tbody>{lines.map((line, index) => {
            const ordered = Number(line.quantity);
            const totals = receiptTotalsByLine.get(line.id) ?? { physical: 0, damaged: 0, accepted: 0 };
            const remaining = Math.max(0, ordered - totals.accepted);
            const quantityNow = Number(quantities[line.id] || 0);
            const damagedNow = Number(damagedQuantities[line.id] || 0);
            const acceptedNow = Math.max(0, quantityNow - damagedNow);
            const label = order.items[index]?.product_name ?? line.product_snapshot?.name ?? `פריט ${index + 1}`;
            return <tr key={line.id} className="border-b last:border-0">
              <td className="py-3 font-semibold">{label}</td><td className="py-3">{ordered}</td><td className="py-3">{totals.physical}</td><td className="py-3">{totals.damaged}</td><td className="py-3 font-semibold text-emerald-700">{totals.accepted}</td><td className="py-3 font-bold">{remaining}</td>
              <td className="py-2"><input aria-label={`כמות פיזית שהגיעה עבור ${label}`} type="number" min="0" step="1" value={quantities[line.id] ?? ""} onChange={(event) => setQuantities((current) => ({ ...current, [line.id]: event.target.value }))} className="w-20 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900" /></td>
              <td className="py-2"><input aria-label={`כמות פגומה עבור ${label}`} type="number" min="0" step="1" value={damagedQuantities[line.id] ?? ""} onChange={(event) => setDamagedQuantities((current) => ({ ...current, [line.id]: event.target.value }))} className="w-20 rounded-lg border border-amber-300 bg-white px-2 py-2 dark:border-amber-800 dark:bg-slate-900" /></td>
              <td className="py-3 font-bold text-emerald-700">{acceptedNow}</td><td className="py-3 font-bold">{Math.max(0, remaining - acceptedNow)}</td>
              <td className="py-2"><input aria-label={`סיבת הפגם עבור ${label}`} value={damageNotes[line.id] ?? ""} onChange={(event) => setDamageNotes((current) => ({ ...current, [line.id]: event.target.value }))} maxLength={1000} placeholder="נדרש אם יש פגם" className="w-36 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900" /></td>
            </tr>;
          })}</tbody></table></div>
        )}
        <label className="block space-y-1"><span className="text-sm font-bold">הערות לקבלה / חוסרים / פריטים פגומים</span><textarea rows={3} maxLength={5000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="לדוגמה: חסרות 2 יחידות, פריט אחד הגיע פגום; נמסר ליוסי ונדרש זיכוי." className="w-full rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
        {message && <p role="status" className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">{message}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-500">{(receiptsQuery.data ?? []).length} קבלות קודמות</div>
          <Button onClick={() => { setMessage(null); createReceipt.mutate(); }} disabled={createReceipt.isPending || !lines.length || receiptsQuery.isLoading || receiptsQuery.isError}>
            <CheckCircle2 size={16} /> {createReceipt.isPending ? "שומר קבלה..." : "רישום קבלת סחורה"}
          </Button>
        </div>
        {(receiptsQuery.data ?? []).length > 0 && <div className="space-y-2 border-t pt-3">{receiptsQuery.data!.map((receipt) => <div key={receipt.id} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700"><div className="flex flex-wrap justify-between gap-2 font-bold"><span>{receipt.receipt_number}</span><span className="text-slate-500">{receipt.received_at ? new Date(receipt.received_at).toLocaleString("he-IL") : "ללא תאריך"}</span></div>{receipt.notes && <p className="mt-1 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{receipt.notes}</p>}<p className="mt-1 text-xs text-slate-500">{receipt.items.length} שורות קבלה · {receipt.items.reduce((sum, item) => sum + Number(item.damaged_quantity ?? 0), 0)} פגומות</p>{receipt.items.filter((item) => Number(item.damaged_quantity ?? 0) > 0).map((item) => <p key={item.id} className="mt-1 text-xs text-amber-700">פריט {item.order_item_id}: {item.damaged_quantity} פגומות — {item.damage_notes || "ללא סיבת פגם"}</p>)}</div>)}</div>}
      </CardContent>
    </Card>
  );
}
