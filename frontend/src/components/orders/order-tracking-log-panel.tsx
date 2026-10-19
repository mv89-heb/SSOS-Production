"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, ClipboardList, MessageSquareText } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type TrackingEventType = "email_sent" | "supplier_confirmed" | "in_transit" | "partial_delivery" | "fully_delivered" | "issue" | "credit_pending" | "other";
type TrackingEvent = { id: number; order_id: number; event_type: TrackingEventType; summary: string; details: string | null; contact_name: string | null; occurred_at: string; next_follow_up_at: string | null; created_by_name: string | null; created_at: string };
type EventsResponse = { success: boolean; events: TrackingEvent[] };

const EVENT_LABELS: Record<TrackingEventType, string> = {
  email_sent: "ההזמנה נשלחה במייל",
  supplier_confirmed: "הספק אישר",
  in_transit: "המשלוח בדרך",
  partial_delivery: "אספקה חלקית",
  fully_delivered: "סופק במלואו",
  issue: "בעיה / פריט פגום",
  credit_pending: "ממתינים לזיכוי",
  other: "עדכון אחר",
};

function localDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("he-IL");
}

export function OrderTrackingLogPanel({ order }: { order: Order }) {
  const queryClient = useQueryClient();
  const [eventType, setEventType] = useState<TrackingEventType>("email_sent");
  const [summary, setSummary] = useState("");
  const [details, setDetails] = useState("");
  const [contactName, setContactName] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [followUpAt, setFollowUpAt] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["order-tracking-events", order.id],
    queryFn: async () => (await apiClient.get<EventsResponse>(`/api/orders/${order.id}/tracking-events`)).data.events,
  });

  const createEvent = useMutation({
    mutationFn: async () => (await apiClient.post<{ success: boolean; event: TrackingEvent }>(
      `/api/orders/${order.id}/tracking-events`,
      {
        event_type: eventType,
        summary: summary.trim(),
        details: details.trim() || null,
        contact_name: contactName.trim() || null,
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null,
        next_follow_up_at: followUpAt ? new Date(followUpAt).toISOString() : null,
      },
    )).data.event,
    onSuccess: async () => {
      setSummary(""); setDetails(""); setContactName(""); setOccurredAt(""); setFollowUpAt("");
      setMessage("העדכון נשמר ביומן ההזמנה.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order-tracking-events", order.id] }),
        queryClient.invalidateQueries({ queryKey: ["order", order.id] }),
        queryClient.invalidateQueries({ queryKey: ["order-reminders"] }),
      ]);
    },
    onError: (error: unknown) => {
      const e = error as { response?: { data?: { message?: string } }; message?: string };
      setMessage(e.response?.data?.message ?? e.message ?? "שמירת העדכון נכשלה.");
    },
  });

  return (
    <Card className="border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader className="border-b border-slate-100 dark:border-slate-800">
        <CardTitle className="flex items-center gap-2 text-base font-extrabold"><ClipboardList size={18} /> יומן מעקב מול הספק</CardTitle>
        <p className="text-sm text-slate-500">רישום פנימי של שיחות, אישורים, משלוחים, חוסרים ובעיות. אפשר להגדיר מועד למעקב הבא.</p>
      </CardHeader>
      <CardContent className="space-y-5 pt-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm"><span className="font-bold">סוג עדכון</span><select value={eventType} onChange={(e) => setEventType(e.target.value as TrackingEventType)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900">{Object.entries(EVENT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="space-y-1 text-sm"><span className="font-bold">איש קשר אצל הספק</span><input value={contactName} onChange={(e) => setContactName(e.target.value)} maxLength={200} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" placeholder="שם הנציג/ה" /></label>
          <label className="space-y-1 text-sm"><span className="font-bold">מועד האירוע</span><input type="datetime-local" value={occurredAt} onChange={(e) => setOccurredAt(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm"><span className="flex items-center gap-1 font-bold"><BellRing size={14} /> תזכורת למעקב הבא</span><input type="datetime-local" value={followUpAt} onChange={(e) => setFollowUpAt(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" /></label>
          <label className="space-y-1 text-sm sm:col-span-2"><span className="font-bold">סיכום קצר *</span><input value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={500} required className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" placeholder="למשל: הספק אישר טלפונית שהמשלוח יגיע מחר" /></label>
          <label className="space-y-1 text-sm sm:col-span-2"><span className="font-bold">פירוט והערות</span><textarea value={details} onChange={(e) => setDetails(e.target.value)} maxLength={5000} rows={2} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900" placeholder="חוסרים, פריט פגום, שיחה על זיכוי או סיכום מול הספק" /></label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-slate-500">מועד מעקב שיוגדר ייכנס גם לתור התזכורות של ההזמנה.</span><Button onClick={() => { setMessage(null); createEvent.mutate(); }} disabled={createEvent.isPending || !summary.trim()}><MessageSquareText size={15} /> {createEvent.isPending ? "שומר..." : "שמירת עדכון"}</Button></div>
        {message && <p role="status" className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800">{message}</p>}
        {eventsQuery.isLoading && <p className="text-sm text-slate-500">טוען יומן מעקב...</p>}
        {eventsQuery.isError && <p className="text-sm text-red-600">טעינת יומן המעקב נכשלה. נסה לרענן.</p>}
        {(eventsQuery.data ?? []).length === 0 && !eventsQuery.isLoading && <p className="rounded-xl border border-dashed p-4 text-sm text-slate-500">עדיין לא נרשמו עדכונים מול הספק להזמנה זו.</p>}
        <div className="space-y-3">{(eventsQuery.data ?? []).map((event) => <div key={event.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><div className="flex flex-wrap items-start justify-between gap-2"><div className="font-bold">{EVENT_LABELS[event.event_type] ?? "עדכון אחר"} · {event.summary}</div><time className="text-xs text-slate-500">{localDateTime(event.occurred_at)}</time></div>{event.contact_name && <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">איש קשר: {event.contact_name}</p>}{event.details && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{event.details}</p>}{event.next_follow_up_at && <p className="mt-2 flex items-center gap-1 text-xs font-semibold text-amber-700 dark:text-amber-300"><BellRing size={13} /> מעקב מתוכנן: {localDateTime(event.next_follow_up_at)}</p>}<p className="mt-2 text-[11px] text-slate-400">נרשם על ידי: {event.created_by_name || "משתמש מערכת"}</p></div>)}</div>
      </CardContent>
    </Card>
  );
}
