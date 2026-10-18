"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, PackageCheck, RefreshCw } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type ReceiptItem = { id: number; receipt_id: number; order_item_id: number; quantity: number };
type Receipt = { id: number; receipt_number: string; status: string; received_at: string | null; notes: string | null; items: ReceiptItem[] };
type ReceiptResponse = { success: boolean; receipts: Receipt[] };
type ReceiptCreateResponse = { success: boolean; receipt: Receipt };

export function OrderReceivingPanel({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const lines = order.order_items ?? [];
  const [quantities, setQuantities] = useState<Record<number, string>>({});
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
  const receivedByLine = useMemo(() => {
    const totals = new Map<number, number>();
    (receiptsQuery.data ?? []).forEach((receipt) => {
      if (receipt.status !== "posted") return;
      receipt.items.forEach((item) => totals.set(item.order_item_id, (totals.get(item.order_item_id) ?? 0) + item.quantity));
    });
    return totals;
  }, [receiptsQuery.data]);
  const createReceipt = useMutation({
    mutationFn: async () => {
      const items = lines.map((line) => ({
        order_item_id: line.id,
        quantity: Number(quantities[line.id] || 0),
      })).filter((item) => Number.isInteger(item.quantity) && item.quantity > 0);
      if (!items.length) throw new Error("יש להזין כמות שהתקבלה לפחות בפריט אחד");
      const { data } = await apiClient.post<ReceiptCreateResponse>(
        `/api/orders/${order.id}/receipts`,
        { items, notes: notes.trim() || null },
        { headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      return data.receipt;
    },
    onSuccess: async (receipt) => {
      setMessage(`הקבלה ${receipt.receipt_number} נשמרה והמלאי עודכן.`);
      setQuantities({});
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
        <p className="text-sm text-slate-500">רשום רק את הכמויות שהגיעו בפועל. אפשר לקלוט אספקה חלקית בכמה קבלות.</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {receiptsQuery.isLoading ? <p className="text-sm text-slate-500">טוען קבלות קודמות...</p> : null}
        {receiptsQuery.isError ? <div className="flex items-center justify-between gap-2 text-sm text-red-600"><span>לא ניתן לטעון קבלות קודמות.</span><Button variant="secondary" onClick={() => receiptsQuery.refetch()}><RefreshCw size={14} /> נסה שוב</Button></div> : null}
        {lines.length === 0 ? <p className="text-sm text-amber-700">לא נמצאו שורות רכש תפעוליות להזמנה זו, ולכן לא ניתן לרשום קבלה דרך המסך.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-right text-sm"><thead><tr className="border-b text-slate-500"><th className="py-2">פריט</th><th className="py-2">הוזמן</th><th className="py-2">התקבל עד כה</th><th className="py-2">נותר</th><th className="py-2">התקבל כעת</th></tr></thead>
            <tbody>{lines.map((line, index) => {
              const ordered = Number(line.quantity);
              const received = receivedByLine.get(line.id) ?? 0;
              const remaining = Math.max(0, ordered - received);
              const label = order.items[index]?.product_name ?? line.product_snapshot?.name ?? `פריט ${index + 1}`;
              return <tr key={line.id} className="border-b last:border-0"><td className="py-3 font-semibold">{label}</td><td className="py-3">{ordered}</td><td className="py-3">{received}</td><td className="py-3">{remaining}</td><td className="py-2"><input aria-label={`כמות שהתקבלה עבור ${label}`} type="number" min="0" max={remaining} step="1" value={quantities[line.id] ?? ""} onChange={(event) => setQuantities((current) => ({ ...current, [line.id]: event.target.value }))} className="w-24 rounded-lg border border-slate-200 bg-white px-2 py-2 dark:border-slate-700 dark:bg-slate-900" /></td></tr>;
            })}</tbody></table></div>
        )}
        <label className="block space-y-1"><span className="text-sm font-bold">הערות לקבלה / חוסרים / פריטים פגומים</span><textarea rows={3} maxLength={5000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="לדוגמה: חסרות 2 יחידות, פריט אחד הגיע פגום; נמסר ליוסי ונדרש זיכוי." className="w-full rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-900" /></label>
        {message && <p role="status" className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">{message}</p>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-500">{(receiptsQuery.data ?? []).length} קבלות קודמות</div>
          <Button onClick={() => { setMessage(null); createReceipt.mutate(); }} disabled={createReceipt.isPending || !lines.length || receiptsQuery.isLoading}>
            <CheckCircle2 size={16} /> {createReceipt.isPending ? "שומר קבלה..." : "רישום קבלת סחורה"}
          </Button>
        </div>
        {(receiptsQuery.data ?? []).length > 0 && <div className="space-y-2 border-t pt-3">{receiptsQuery.data!.map((receipt) => <div key={receipt.id} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700"><div className="flex flex-wrap justify-between gap-2 font-bold"><span>{receipt.receipt_number}</span><span className="text-slate-500">{receipt.received_at ? new Date(receipt.received_at).toLocaleString("he-IL") : "ללא תאריך"}</span></div>{receipt.notes && <p className="mt-1 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{receipt.notes}</p>}<p className="mt-1 text-xs text-slate-500">{receipt.items.length} שורות קבלה</p></div>)}</div>}
      </CardContent>
    </Card>
  );
}
