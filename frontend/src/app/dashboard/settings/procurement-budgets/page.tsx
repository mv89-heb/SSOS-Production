"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Pencil, Plus, ShieldAlert, Trash2, Wallet } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type Budget = {
  id: number; scope_type: "department" | "project"; scope_value: string;
  period_type: "weekly" | "monthly"; period_start: string; amount: number;
  currency: string; enforcement_mode: "warn" | "block"; active: boolean;
  spent_amount: number; remaining_amount: number;
};

function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function periodStart(type: "weekly" | "monthly", source = new Date()) {
  const date = new Date(source);
  date.setHours(12, 0, 0, 0);
  if (type === "weekly") date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  else date.setDate(1);
  return isoDate(date);
}
function money(currency: string, value: number) {
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 0 }).format(value); }
  catch { return `${value.toFixed(2)} ${currency}`; }
}

export default function ProcurementBudgetsPage() {
  const { user } = useAuth();
  const canManage = permissions.canApproveOrders(user);
  const queryClient = useQueryClient();
  const [scopeType, setScopeType] = useState<"department" | "project">("department");
  const [scopeValue, setScopeValue] = useState("");
  const [periodType, setPeriodType] = useState<"weekly" | "monthly">("monthly");
  const [periodStartValue, setPeriodStartValue] = useState(periodStart("monthly"));
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("ILS");
  const [enforcementMode, setEnforcementMode] = useState<"warn" | "block">("warn");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const budgetsQuery = useQuery({
    queryKey: ["procurement-budgets"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ success: boolean; budgets: Budget[] }>("/api/procurement-budgets");
      return data.budgets;
    },
    enabled: canManage,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        scope_type: scopeType,
        scope_value: scopeValue.trim(),
        period_type: periodType,
        period_start: periodStartValue,
        amount: Number(amount),
        currency,
        enforcement_mode: enforcementMode,
        active: true,
      };
      if (editingId) {
        const { data } = await apiClient.put<{ success: boolean; budget: Budget }>(`/api/procurement-budgets/${editingId}`, payload);
        return data.budget;
      }
      const { data } = await apiClient.post<{ success: boolean; budget: Budget }>("/api/procurement-budgets", payload);
      return data.budget;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["procurement-budgets"] });
      setScopeValue(""); setAmount(""); setEditingId(null); setError("");
    },
    onError: (err: any) => setError(err?.response?.data?.message || "שמירת התקציב נכשלה"),
  });

  const deactivateMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.delete(`/api/procurement-budgets/${id}`);
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["procurement-budgets"] }),
    onError: (err: any) => setError(err?.response?.data?.message || "לא ניתן להשבית את התקציב"),
  });

  const budgets = budgetsQuery.data || [];
  const activeTotal = useMemo(() => budgets.length, [budgets]);

  function resetForm() {
    setScopeType("department"); setScopeValue(""); setPeriodType("monthly");
    setPeriodStartValue(periodStart("monthly")); setAmount(""); setCurrency("ILS");
    setEnforcementMode("warn"); setEditingId(null); setError("");
  }

  function editBudget(budget: Budget) {
    setEditingId(budget.id); setScopeType(budget.scope_type); setScopeValue(budget.scope_value);
    setPeriodType(budget.period_type); setPeriodStartValue(budget.period_start);
    setAmount(String(budget.amount)); setCurrency(budget.currency);
    setEnforcementMode(budget.enforcement_mode); setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!scopeValue.trim() || !amount || !Number.isFinite(Number(amount)) || Number(amount) <= 0) {
      setError("יש להזין שם מחלקה/פרויקט וסכום תקציב חיובי");
      return;
    }
    if (periodStartValue !== periodStart(periodType, new Date(periodStartValue + "T12:00:00"))) {
      setError(periodType === "weekly" ? "תקציב שבועי חייב להתחיל ביום שני" : "תקציב חודשי חייב להתחיל ביום הראשון בחודש");
      return;
    }
    saveMutation.mutate();
  }

  if (!canManage) {
    return <div className="mx-auto max-w-3xl p-6"><Card><CardContent className="p-8 text-center"><ShieldAlert className="mx-auto mb-3 h-8 w-8 text-amber-600" /><h1 className="text-lg font-bold">אין הרשאה לניהול תקציבים</h1><p className="mt-2 text-sm text-slate-500">ניהול תקציבים זמין למנהלים ולמנהלי מערכת בלבד.</p><Link className="mt-4 inline-block text-primary underline" href="/dashboard/settings">חזרה להגדרות</Link></CardContent></Card></div>;
  }

  return <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6" dir="rtl">
    <div className="flex items-center gap-3"><Link href="/dashboard/settings" className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><ArrowRight className="h-5 w-5" /></Link><div><h1 className="text-2xl font-black text-slate-900 dark:text-white">תקציבי רכש</h1><p className="mt-1 text-sm text-slate-500">ניהול תקציבים שבועיים וחודשיים לפי מחלקה או פרויקט</p></div><span className="mr-auto rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 dark:bg-slate-800">{activeTotal} תקציבים פעילים</span></div>

    <Card className="border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Plus className="h-4 w-4" />{editingId ? "עריכת תקציב" : "הגדרת תקציב חדש"}</CardTitle></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="space-y-1 text-sm font-semibold">סוג שיוך<select value={scopeType} onChange={(e) => setScopeType(e.target.value as "department" | "project")} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"><option value="department">מחלקה</option><option value="project">פרויקט</option></select></label>
          <label className="space-y-1 text-sm font-semibold">שם המחלקה / הפרויקט<input required maxLength={120} value={scopeValue} onChange={(e) => setScopeValue(e.target.value)} placeholder="לדוגמה: מטבח" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950" /></label>
          <label className="space-y-1 text-sm font-semibold">תקופת תקציב<select value={periodType} onChange={(e) => { const next = e.target.value as "weekly" | "monthly"; setPeriodType(next); setPeriodStartValue(periodStart(next)); }} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"><option value="monthly">חודשי</option><option value="weekly">שבועי</option></select></label>
          <label className="space-y-1 text-sm font-semibold">תחילת תקופה<input required type="date" value={periodStartValue} onChange={(e) => setPeriodStartValue(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950" /><span className="block text-[11px] font-normal text-slate-500">{periodType === "weekly" ? "יום שני בלבד" : "היום הראשון בחודש בלבד"}</span></label>
          <label className="space-y-1 text-sm font-semibold">סכום תקציב<input required type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950" /></label>
          <label className="space-y-1 text-sm font-semibold">מטבע<input required minLength={3} maxLength={3} pattern="[A-Za-z]{3}" value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} placeholder="ILS" className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 uppercase dark:border-slate-700 dark:bg-slate-950" /><span className="block text-[11px] font-normal text-slate-500">קוד מטבע בן 3 אותיות</span></label>
          <label className="space-y-1 text-sm font-semibold">מדיניות חריגה<select value={enforcementMode} onChange={(e) => setEnforcementMode(e.target.value as "warn" | "block")} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-950"><option value="warn">אזהרה — ניתן להגיש</option><option value="block">חסימה — עקיפה מנומקת למנהל בלבד</option></select></label>
          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4"><Button type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? "שומר..." : editingId ? "שמירת שינויים" : "יצירת תקציב"}</Button>{editingId && <Button type="button" variant="outline" onClick={resetForm}>ביטול עריכה</Button>}</div>
        </form>
        {error && <p role="alert" className="mt-3 text-sm font-semibold text-red-600">{error}</p>}
      </CardContent>
    </Card>

    <Card className="border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Wallet className="h-4 w-4" />תקציבים פעילים</CardTitle></CardHeader>
      <CardContent>
        {budgetsQuery.isLoading ? <p className="py-8 text-center text-sm text-slate-500">טוען תקציבים...</p> :
          budgetsQuery.isError ? <p role="alert" className="py-8 text-center text-sm text-red-600">טעינת התקציבים נכשלה</p> :
          budgets.length === 0 ? <div className="py-10 text-center"><CalendarDays className="mx-auto mb-3 h-8 w-8 text-slate-400" /><p className="font-bold">עדיין לא הוגדרו תקציבים</p><p className="mt-1 text-sm text-slate-500">לאחר הגדרת תקציב, המערכת תחשב התחייבויות קיימות לפני הגשת הזמנה.</p></div> :
          <div className="grid gap-3 md:grid-cols-2">{budgets.map((budget: Budget) => <div key={budget.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="flex items-start justify-between gap-3"><div><p className="font-bold">{budget.scope_type === "department" ? "מחלקה" : "פרויקט"}: {budget.scope_value}</p><p className="mt-1 text-xs text-slate-500">{budget.period_type === "weekly" ? "שבועי" : "חודשי"} · מתחיל {budget.period_start} · {budget.currency}</p></div><span className={budget.enforcement_mode === "block" ? "rounded-full bg-red-50 px-2 py-1 text-[11px] font-bold text-red-700 dark:bg-red-950/40 dark:text-red-300" : "rounded-full bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"}>{budget.enforcement_mode === "block" ? "חסימה" : "אזהרה"}</span></div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-sm"><div><p className="text-xs text-slate-500">תקציב</p><p className="font-black">{money(budget.currency, budget.amount)}</p></div><div><p className="text-xs text-slate-500">התחייבויות</p><p className="font-bold">{money(budget.currency, budget.spent_amount)}</p></div><div><p className="text-xs text-slate-500">יתרה</p><p className={budget.remaining_amount < 0 ? "font-black text-red-700" : "font-bold"}>{money(budget.currency, budget.remaining_amount)}</p></div></div>
            <div className="mt-4 flex gap-2"><Button type="button" variant="outline" onClick={() => editBudget(budget)}><Pencil className="ml-1 h-3.5 w-3.5" />עריכה</Button><Button type="button" variant="ghost" className="text-red-600" disabled={deactivateMutation.isPending} onClick={() => { if (window.confirm("להשבית את התקציב? ההזמנות שכבר הוגשו לא ישתנו.")) deactivateMutation.mutate(budget.id); }}><Trash2 className="ml-1 h-3.5 w-3.5" />השבתה</Button></div>
          </div>)}</div>}
      </CardContent>
    </Card>
    <p className="text-xs leading-5 text-slate-500">התחייבויות מחושבות מהזמנות שהוגשו לאישור, אושרו, נשלחו או הושלמו. טיוטות, חשבוניות וקבלות אינן נספרות שוב. סכומים נשארים מופרדים לפי מטבע — אין המרת מטבע אוטומטית.</p>
  </div>;
}
