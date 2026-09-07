"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, ExternalLink, LogOut, RefreshCw } from "lucide-react";
import { googleCalendarService } from "@/services/google-calendar-service";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";

export default function GoogleCalendarSettingsPage() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["google-calendar-status"], queryFn: googleCalendarService.status });
  const disconnect = useMutation({ mutationFn: googleCalendarService.disconnect, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["google-calendar-status"] }) });
  const selectCalendar = useMutation({ mutationFn: googleCalendarService.selectCalendar, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["google-calendar-status"] }) });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google_calendar") === "connected") queryClient.invalidateQueries({ queryKey: ["google-calendar-status"] });
  }, [queryClient]);

  const data = status.data;
  const connection = data?.connection;

  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black text-slate-900 dark:text-white">Google Calendar</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">חיבור היומן האישי שלך לתזכורות המעקב של SSOS.</p>
      </div>

      <Card className="border-indigo-100 dark:border-indigo-900/40">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarDays className="h-5 w-5 text-indigo-600" /> סנכרון תזכורות</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          {!data?.configured && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">חיבור Google Calendar עדיין לא הופעל בשרת. לאחר הגדרת Google OAuth ב-Render, כפתור החיבור יהיה זמין.</div>}
          {data?.configured && !connection && <div className="space-y-4"><p className="text-sm text-slate-600 dark:text-slate-300">לאחר החיבור, כל תזכורת שתופעל ב-SSOS תיצור אירוע ביומן, כולל קישור להזמנה והתראה של Google Calendar.</p><Button onClick={() => { window.location.href = googleCalendarService.connectUrl(); }}><ExternalLink className="h-4 w-4" /> התחבר ל-Google Calendar</Button></div>}
          {connection && <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><div><p className="text-sm font-black text-emerald-800">Google Calendar מחובר</p><p className="text-xs text-emerald-700">{connection.google_email || "חשבון Google מחובר"}</p></div></div>
            <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end"><div><label className="mb-1 block text-xs font-bold text-slate-500">יומן לתזכורות</label><Select value={connection.calendar_id} onChange={(e) => selectCalendar.mutate(e.target.value)} disabled={selectCalendar.isPending || status.isFetching}><option value={connection.calendar_id}>{connection.calendar_name || connection.calendar_id}</option>{data.calendars.filter((item) => item.id !== connection.calendar_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></div><Button variant="secondary" onClick={() => status.refetch()} disabled={status.isFetching}><RefreshCw className={`h-4 w-4 ${status.isFetching ? "animate-spin" : ""}`} /> רענן יומנים</Button></div>
            <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => disconnect.mutate()} disabled={disconnect.isPending}><LogOut className="h-4 w-4" /> נתק את Google Calendar</Button></div>
          </div>}
        </CardContent>
      </Card>

      <Card><CardContent className="space-y-2 p-5 text-sm text-slate-600 dark:text-slate-300"><p className="font-bold text-slate-900 dark:text-white">מה קורה אחרי החיבור?</p><ul className="list-disc space-y-1 pr-5"><li>הפעלת תזכורת יוצרת אירוע ביומן עם שם הספק וההזמנה.</li><li>דחיית תזכורת מעדכנת את אותו אירוע במקום ליצור כפילות.</li><li>סימון התזכורת כטופלה מסיר את האירוע מהיומן.</li><li>Gemini יכול לבחור את מועד המעקב מתוך מועדים בטוחים שהמערכת חישבה.</li></ul></CardContent></Card>
    </div>
  );
}
