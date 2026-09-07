"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, Clock3, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

const TIMEZONE = "Asia/Jerusalem";

function toLocalInputParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    time: `${get("hour")}:${get("minute")}`,
  };
}

function localJerusalemToIso(dateValue: string, timeValue: string) {
  if (!dateValue || !timeValue) return "";
  const candidate = new Date(`${dateValue}T${timeValue}:00+03:00`);
  return Number.isNaN(candidate.getTime()) ? "" : candidate.toISOString();
}

function minutesFromNow(minutes: number) {
  return toLocalInputParts(new Date(Date.now() + minutes * 60_000));
}

export type ManualReminderPickerProps = {
  value?: string;
  onChange: (isoValue: string) => void;
  disabled?: boolean;
};

export function ManualReminderPicker({ value = "", onChange, disabled = false }: ManualReminderPickerProps) {
  const initial = useMemo(() => (value ? toLocalInputParts(new Date(value)) : minutesFromNow(60)), [value]);
  const [dateValue, setDateValue] = useState(initial.date);
  const [timeValue, setTimeValue] = useState(initial.time);
  const [error, setError] = useState("");

  useEffect(() => {
    setDateValue(initial.date);
    setTimeValue(initial.time);
  }, [initial.date, initial.time]);

  const update = (nextDate: string, nextTime: string) => {
    setDateValue(nextDate);
    setTimeValue(nextTime);
    const iso = localJerusalemToIso(nextDate, nextTime);
    if (!iso) return;
    if (new Date(iso).getTime() <= Date.now()) {
      setError("בחר תאריך ושעה שטרם עברו.");
      return;
    }
    setError("");
    onChange(iso);
  };

  const applyQuick = (minutes: number) => {
    const next = minutesFromNow(minutes);
    update(next.date, next.time);
  };

  const applyTomorrow = () => {
    const next = new Date(Date.now() + 24 * 60 * 60_000);
    const parts = toLocalInputParts(next);
    update(parts.date, "09:00");
  };

  return (
    <div className="space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-900/60 dark:bg-indigo-950/20">
      <div className="flex items-center gap-2">
        <CalendarDays className="h-4 w-4 text-indigo-600" />
        <div>
          <div className="text-sm font-extrabold text-slate-900 dark:text-white">מועד התזכורת</div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400">אזור זמן: {TIMEZONE}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-xs font-bold text-slate-700 dark:text-slate-200">תאריך</span>
          <input type="date" value={dateValue} disabled={disabled} onChange={(event) => update(event.target.value, timeValue)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-900 outline-none ring-indigo-200 transition focus:border-indigo-400 focus:ring-2 dark:border-slate-700 dark:bg-slate-900 dark:text-white" />
        </label>
        <label className="space-y-1.5">
          <span className="flex items-center gap-1 text-xs font-bold text-slate-700 dark:text-slate-200"><Clock3 className="h-3.5 w-3.5" /> שעה</span>
          <input type="time" value={timeValue} disabled={disabled} onChange={(event) => update(dateValue, event.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-900 outline-none ring-indigo-200 transition focus:border-indigo-400 focus:ring-2 dark:border-slate-700 dark:bg-slate-900 dark:text-white" />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" className="min-h-9 text-xs" disabled={disabled} onClick={() => applyQuick(5)}><Sparkles className="h-3.5 w-3.5" />בעוד 5 דקות</Button>
        <Button type="button" variant="secondary" className="min-h-9 text-xs" disabled={disabled} onClick={() => applyQuick(60)}>בעוד שעה</Button>
        <Button type="button" variant="secondary" className="min-h-9 text-xs" disabled={disabled} onClick={applyTomorrow}>מחר ב־09:00</Button>
      </div>
      {error && <p className="text-xs font-bold text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
