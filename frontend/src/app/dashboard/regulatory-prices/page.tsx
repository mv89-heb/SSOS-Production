"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Egg, ShieldCheck, AlertTriangle, History, RefreshCw } from "lucide-react";
import { regulatoryPricesService } from "@/services/regulatory-prices-service";

const money = (value: number) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(value);
const sizeLabels: Record<string, string> = { M: "M – מדיום", L: "L – גדול", XL: "XL – ענק" };

export default function RegulatoryPricesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["regulatory-prices", "eggs"], queryFn: regulatoryPricesService.getEggPrices });
  const [effectiveDate, setEffectiveDate] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [sourceUrl, setSourceUrl] = useState("https://www.gov.il/he/Departments/ministry_of_agriculture_and_food_security/govil-landing-page");
  const [sourceTitle, setSourceTitle] = useState("משרד החקלאות וביטחון המזון – עדכון מחירי ביצים");
  const [changePercent, setChangePercent] = useState("2.1");
  const [prices, setPrices] = useState({ M: "13.40", L: "14.54", XL: "15.81" });
  const [notice, setNotice] = useState("");
  const mutation = useMutation({
    mutationFn: regulatoryPricesService.addEggRelease,
    onSuccess: async () => {
      setNotice("העדכון הרשמי נשמר בהיסטוריה. מחירי הספקים והקטלוג לא שונו.");
      await queryClient.invalidateQueries({ queryKey: ["regulatory-prices", "eggs"] });
    },
    onError: (error: any) => setNotice(error?.response?.data?.message || "לא ניתן לשמור את העדכון."),
  });
  const data = query.data;
  const current = data?.current_release ?? [];
  const history = data?.history ?? [];
  const matches = data?.matched_products ?? [];

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setNotice("");
    mutation.mutate({
      effective_date: effectiveDate,
      published_at: publishedAt || undefined,
      source_url: sourceUrl,
      source_title: sourceTitle,
      change_percent: changePercent ? Number(changePercent) : undefined,
      items: (["M", "L", "XL"] as const).map((size_code) => ({ size_code, max_consumer_price: Number(prices[size_code]) })),
    });
  };

  return <div dir="rtl" className="space-y-6">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><div className="flex items-center gap-2 text-sm font-semibold text-indigo-600"><Egg size={18}/> בקרה רגולטורית</div><h1 className="mt-1 text-2xl font-black text-slate-900 dark:text-white">מחירי ביצים בפיקוח</h1><p className="mt-1 text-sm text-slate-500">מחירי תקרה רשמיים לצרכן, היסטוריית עדכונים ומיפוי מוצרי הקטלוג.</p></div>
      <button type="button" onClick={() => query.refetch()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold dark:border-slate-700 dark:bg-slate-900"><RefreshCw size={16}/> רענן נתונים</button>
    </header>

    <section className="rounded-2xl border border-indigo-200 bg-indigo-50/70 p-4 dark:border-indigo-900 dark:bg-indigo-950/20">
      <div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 shrink-0 text-indigo-600" size={21}/><div><h2 className="font-bold text-slate-900 dark:text-white">המחיר המפוקח אינו מחיר הרכש</h2><p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">הנתונים מתייחסים למחיר מרבי לצרכן עבור אריזת 12 ביצים. הם אינם מחליפים מחיר ספק, הצעת מחיר או מחיר בהזמנת רכש. ביצי חופש, אורגניות וביצים מועשרות באומגה מוחרגות מהפיקוח ולא יסווגו כמפוקחות.</p></div></div>
    </section>

    {query.isLoading && <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-950">טוען נתוני פיקוח…</div>}
    {query.isError && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">לא ניתן לטעון את נתוני הפיקוח. <button className="font-bold underline" onClick={() => query.refetch()}>נסה שוב</button></div>}

    {!query.isLoading && !query.isError && <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">מעקב אוטומטי אחר הודעות ממשלתיות</h2><p className="mt-1 text-xs text-slate-500">GitHub Actions בודק מדי יום את פרסומי משרד החקלאות ושולח התראה למנהלי המערכת כשמזוהה הודעה חדשה. המעקב אינו משנה מחירים.</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">{data?.monitor?.last_checked_at ? "בדיקה אחרונה: " + new Date(data.monitor.last_checked_at).toLocaleString("he-IL") : "טרם בוצעה בדיקה"}</span></div>{data?.monitor?.last_article_title && <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">הודעה אחרונה שזוהתה: {data.monitor.last_article_title} {data.monitor.last_article_url && <a href={data.monitor.last_article_url} target="_blank" rel="noreferrer" className="font-semibold text-indigo-600 hover:underline">פתיחת מקור</a>}</p>}{data?.monitor?.last_error && <p role="status" className="mt-2 text-xs text-amber-700 dark:text-amber-300">הערת ניטור: {data.monitor.last_error}</p>}</section>}

    {!query.isLoading && !query.isError && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">מחירים בתוקף</h2><p className="mt-1 text-xs text-slate-500">החל מ־{data?.effective_date ? new Date(data.effective_date + "T00:00:00").toLocaleDateString("he-IL") : "לא הוגדר"}</p></div><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">מחיר מרבי לצרכן · 12 ביצים</span></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">{(["M", "L", "XL"] as const).map((size) => { const row = current.find((item) => item.size_code === size); return <div key={size} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><div className="text-sm font-bold text-slate-500">{sizeLabels[size]}</div><div className="mt-2 text-3xl font-black tabular-nums text-slate-900 dark:text-white">{row ? money(row.max_consumer_price) : "—"}</div>{row?.change_percent != null && <div className="mt-1 text-xs text-slate-500">שינוי שפורסם: {row.change_percent}%</div>}</div>; })}</div>
      {current[0]?.source_url && <a href={current[0].source_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:underline">מקור ממשלתי <ExternalLink size={14}/></a>}
    </section>}

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between gap-3"><div><h2 className="font-bold">מוצרי ביצים בקטלוג</h2><p className="mt-1 text-xs text-slate-500">התאמה לפי שם מוצר בלבד; סיווג לא ודאי מוצג לבדיקה ולא משנה נתוני מוצר.</p></div><span className="text-xs text-slate-500">{matches.length} מוצרים</span></div>
      {matches.length === 0 ? <p className="mt-4 text-sm text-slate-500">לא נמצאו מוצרי ביצים בקטלוג.</p> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[680px] text-right text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-2">מוצר</th><th className="p-2">ספק</th><th className="p-2">סיווג</th><th className="p-2">תקרת מחיר לצרכן</th><th className="p-2">מחיר בקטלוג</th></tr></thead><tbody>{matches.map((item) => <tr key={item.product_id} className="border-b border-slate-100 dark:border-slate-800"><td className="p-2 font-semibold">{item.product_name}</td><td className="p-2">{item.supplier_name || "—"}</td><td className="p-2">{item.regulated ? sizeLabels[item.size_code!] : <span className="text-amber-700">{item.exclusion_reason || "נדרשת בדיקה"}</span>}</td><td className="p-2 tabular-nums">{item.max_consumer_price != null ? money(item.max_consumer_price) : "—"}</td><td className="p-2 tabular-nums">{item.product_current_price != null ? money(item.product_current_price) : "—"}</td></tr>)}</tbody></table></div>}
      <p className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-500"><AlertTriangle size={15} className="mt-0.5 shrink-0"/>מחיר הקטלוג מוצג להשוואה בלבד. המערכת אינה משנה אותו בעקבות עדכון רגולטורי.</p>
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center gap-2"><History size={18} className="text-indigo-600"/><h2 className="font-bold">היסטוריית מחירים מפוקחים</h2></div>
      <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[620px] text-right text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-2">תאריך תחילה</th><th className="p-2">גודל</th><th className="p-2">מחיר לצרכן</th><th className="p-2">שינוי</th><th className="p-2">מקור</th></tr></thead><tbody>{history.map((row) => <tr key={row.id} className="border-b border-slate-100 dark:border-slate-800"><td className="p-2">{new Date(row.effective_date + "T00:00:00").toLocaleDateString("he-IL")}</td><td className="p-2">{sizeLabels[row.size_code]}</td><td className="p-2 font-semibold tabular-nums">{money(row.max_consumer_price)}</td><td className="p-2">{row.change_percent != null ? row.change_percent + "%" : "—"}</td><td className="p-2"><a href={row.source_url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">מסמך מקור</a></td></tr>)}</tbody></table></div>
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <h2 className="font-bold">רישום עדכון רשמי עתידי</h2><p className="mt-1 text-sm text-slate-500">לאחר פרסום צו או הודעה ממשלתית חדשה, מנהל יכול לתעד את שלושת המחירים. הרשומה מתווספת להיסטוריה ואינה מעדכנת מחירי ספקים.</p>
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-semibold">תאריך תחילת תוקף<input required type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>
        <label className="text-sm font-semibold">תאריך פרסום<input type="date" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>
        {(["M", "L", "XL"] as const).map((size) => <label key={size} className="text-sm font-semibold">מחיר {sizeLabels[size]} (₪ / 12 ביצים)<input required type="number" min="0.01" max="1000" step="0.01" value={prices[size]} onChange={(e) => setPrices((current) => ({ ...current, [size]: e.target.value }))} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>)}
        <label className="text-sm font-semibold">אחוז שינוי<input type="number" step="0.001" value={changePercent} onChange={(e) => setChangePercent(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>
        <label className="text-sm font-semibold sm:col-span-2">כותרת המקור<input required value={sourceTitle} onChange={(e) => setSourceTitle(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>
        <label className="text-sm font-semibold sm:col-span-2">קישור ממשלתי<input required type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"/></label>
        <div className="sm:col-span-2"><button type="submit" disabled={mutation.isPending} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white disabled:opacity-50">{mutation.isPending ? "שומר…" : "שמור עדכון רשמי"}</button>{notice && <p role="status" className="mt-2 text-sm text-slate-600">{notice}</p>}</div>
      </form>
    </section>
  </div>;
}
