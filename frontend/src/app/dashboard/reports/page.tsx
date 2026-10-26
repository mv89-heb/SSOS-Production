"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Boxes, CalendarDays, CircleDollarSign, Package, RefreshCw, ShoppingCart, TrendingUp, Truck } from "lucide-react";
import { inventoryService } from "@/services/inventory-service";
import { orderService } from "@/services/order-service";
import { catalogService } from "@/services/catalog-service";
import type { Product } from "@/types";

const money = (value: number) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 }).format(value);
const qty = (value: number) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(value);
const monthKey = (value: string) => { const d = new Date(value); return Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`; };
const monthLabel = (key: string) => { const [y,m] = key.split("-").map(Number); return new Intl.DateTimeFormat("he-IL", { month: "short" }).format(new Date(y,m-1,1)); };

function Kpi({ title, value, detail, icon: Icon, href }: { title: string; value: string; detail: string; icon: typeof Package; href?: string }) {
  const body = <div className="h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-950">
    <div className="flex items-center justify-between gap-3"><span className="text-sm font-bold text-slate-500">{title}</span><span className="rounded-xl bg-indigo-50 p-2 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"><Icon size={19}/></span></div>
    <div className="mt-3 text-2xl font-black tracking-tight text-slate-900 dark:text-white">{value}</div><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
  </div>;
  return href ? <Link href={href} className="block">{body}</Link> : body;
}
function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><header className="border-b border-slate-100 px-5 py-4 dark:border-slate-800"><h2 className="font-black text-slate-900 dark:text-white">{title}</h2>{subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}</header><div className="p-5">{children}</div></section>;
}
function Empty({ text }: { text: string }) { return <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500 dark:bg-slate-900">{text}</p>; }

export default function ReportsInsightsPage() {
  const [period, setPeriod] = useState("30");
  const [supplier, setSupplier] = useState("all");
  const [category, setCategory] = useState("all");
  const [risk, setRisk] = useState("all");
  const productsQuery = useQuery({ queryKey: ["reports", "products"], queryFn: () => catalogService.listProducts(undefined, true), staleTime: 30000 });
  const suppliersQuery = useQuery({ queryKey: ["reports", "suppliers"], queryFn: () => catalogService.listSuppliers(true), staleTime: 30000 });
  const ordersQuery = useQuery({ queryKey: ["reports", "orders"], queryFn: () => orderService.getOrders(), staleTime: 30000 });
  const inventoryQuery = useQuery({ queryKey: ["reports", "inventory"], queryFn: () => inventoryService.getSummary(), staleTime: 30000 });
  const recommendationsQuery = useQuery({ queryKey: ["reports", "recommendations", period], queryFn: () => inventoryService.getRecommendations({ lookback_days: Number(period), limit: 1000 }), staleTime: 30000 });
  const loading = [productsQuery, suppliersQuery, ordersQuery, inventoryQuery, recommendationsQuery].some(q => q.isLoading);
  const error = [productsQuery, suppliersQuery, ordersQuery, inventoryQuery, recommendationsQuery].find(q => q.isError);
  const products = productsQuery.data ?? [];
  const suppliers = suppliersQuery.data ?? [];
  const orders = ordersQuery.data ?? [];
  const recommendations = recommendationsQuery.data ?? [];
  const today = new Date();
  const fromDate = new Date(today.getTime() - Number(period) * 86400000);
  const categories = Array.from(new Set(products.map(p => p.category?.trim()).filter((v): v is string => Boolean(v)))).sort((a,b)=>a.localeCompare(b,"he"));
  const visibleProducts = products.filter(p => (supplier === "all" || String(p.supplier_id) === supplier) && (category === "all" || p.category === category));
  const recommendationMap = new Map(recommendations.map(r => [r.product_id, r]));
  const visibleRecommendations = recommendations.filter(r => {
    const p = products.find(x => x.id === r.product_id);
    return (!p || (supplier === "all" || String(p.supplier_id) === supplier) && (category === "all" || p.category === category)) && (risk === "all" || r.status === risk);
  });
  const stockValue = visibleProducts.reduce((sum,p) => sum + Math.max(0, Number(p.current_stock ?? 0)) * Math.max(0, Number(p.current_price ?? 0)), 0);
  const riskCount = visibleRecommendations.filter(r => r.status === "urgent" || r.status === "reorder" || r.status === "insufficient_data").length;
  const monthSpend = orders.filter(o => ["approved","sent","completed"].includes(o.status) && monthKey(o.created_at) === monthKey(today.toISOString())).reduce((sum,o)=>sum+Number(o.final_total ?? 0),0);
  const monthlySpend = useMemo(() => {
    const keys = Array.from({length:6},(_,i)=>{const d=new Date(today.getFullYear(),today.getMonth()-(5-i),1);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;});
    return keys.map(key=>({key,label:monthLabel(key),amount:orders.filter(o=>["approved","sent","completed"].includes(o.status)&&monthKey(o.created_at)===key).reduce((s,o)=>s+Number(o.final_total??0),0)}));
  }, [orders]);
  const maxSpend = Math.max(1,...monthlySpend.map(x=>x.amount));
  const categoryStats = useMemo(() => {
    const groups = new Map<string,number>();
    visibleProducts.forEach(p=>{const key=p.category?.trim()||"ללא קטגוריה";groups.set(key,(groups.get(key)||0)+Math.max(0,Number(p.current_stock??0))*Math.max(0,Number(p.current_price??0)));});
    return Array.from(groups.entries()).map(([name,value])=>({name,value})).sort((a,b)=>b.value-a.value).slice(0,7);
  }, [visibleProducts]);
  const maxCategory = Math.max(1,...categoryStats.map(x=>x.value));
  const deadStockCandidates = visibleProducts.filter(p => {
    const rec = recommendationMap.get(p.id);
    return rec?.average_daily_usage === 0 && Number(p.current_stock ?? 0) > 0 && rec.stock_checks_in_period >= 2;
  });
  const highConsumption = visibleRecommendations.filter(r => r.data_ready && r.average_daily_usage > 0).sort((a,b)=>b.average_daily_usage-a.average_daily_usage).slice(0,4);
  const dateRange = `${fromDate.toLocaleDateString("he-IL")} – ${today.toLocaleDateString("he-IL")}`;
  return <main dir="rtl" className="mx-auto max-w-[1600px] space-y-6 pb-12">
    <header className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950 lg:flex-row lg:items-end lg:justify-between">
      <div><div className="mb-2 flex items-center gap-2 text-sm font-bold text-indigo-700 dark:text-indigo-300"><BarChart3 size={18}/> ניתוח נתונים מבוסס נתוני המערכת</div><h1 className="text-3xl font-black text-slate-950 dark:text-white">דוחות ותובנות</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">תמונת מצב מאוחדת של מלאי, צריכה ורכש. הנתונים נשלפים ממסכי המלאי, הקטלוג וההזמנות — בלי להציג הערכות כאילו היו נתונים בפועל.</p></div>
      <div className="flex flex-wrap items-center gap-2"><label className="text-xs font-bold text-slate-500" htmlFor="report-period">תקופת צריכה</label><select id="report-period" value={period} onChange={e=>setPeriod(e.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="7">7 ימים</option><option value="30">30 ימים</option><option value="60">60 ימים</option><option value="90">90 ימים</option></select><button onClick={()=>{void Promise.all([productsQuery.refetch(),suppliersQuery.refetch(),ordersQuery.refetch(),inventoryQuery.refetch(),recommendationsQuery.refetch()]);}} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"><RefreshCw size={15}/> רענון</button></div>
    </header>
    {error && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"><span>חלק מנתוני הדוח לא נטענו. נסה לרענן; לא נציג נתונים חסרים כאילו הם אפס.</span><button onClick={()=>{void Promise.all([productsQuery.refetch(),suppliersQuery.refetch(),ordersQuery.refetch(),inventoryQuery.refetch(),recommendationsQuery.refetch()]);}} className="font-black underline">נסה שוב</button></div>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Kpi title="שווי מלאי נוכחי" value={loading?"…":money(stockValue)} detail="מלאי נוכחי × מחיר מוצר; השוואה לחודש קודם אינה זמינה במקורות הקיימים." icon={Boxes} href="/dashboard/inventory"/>
      <Kpi title="פריטים הדורשים תשומת לב" value={loading?"…":qty(riskCount)} detail="דחוף, נדרשת הזמנה או שחסרים נתונים אמינים לתכנון." icon={AlertTriangle} href="/dashboard/inventory"/>
      <Kpi title="הוצאות רכש החודש" value={loading?"…":money(monthSpend)} detail="הזמנות שאושרו, נשלחו או הושלמו לפי תאריך יצירת ההזמנה." icon={CircleDollarSign} href="/dashboard/orders"/>
      <Kpi title="ניצולת תקציב" value="לא מוגדר" detail="אין כרגע יעד תקציב מאושר זמין לחישוב אחוז ניצול אמין." icon={TrendingUp}/>
    </div>
    <Panel title="תובנות ופעולות מומלצות" subtitle={`מבוסס על נתונים קיימים לתקופה: ${dateRange}`}>
      {loading ? <Empty text="טוען נתוני צריכה ומלאי…"/> : <div className="grid gap-3 lg:grid-cols-2">
        {highConsumption.length>0 ? highConsumption.slice(0,2).map(r=><div key={r.product_id} className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 dark:border-blue-900 dark:bg-blue-950/20"><div className="flex items-start gap-3"><TrendingUp className="mt-0.5 shrink-0 text-blue-700" size={19}/><div className="min-w-0"><p className="font-black">{r.product_name}</p><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">קצב צריכה ממוצע: {qty(r.average_daily_usage)} ליום{r.average_daily_usage_cartons!=null? ` · ${qty(r.average_daily_usage_cartons)} קרטונים ליום`:""}. כמות מומלצת להזמנה: {qty(r.recommended_order_cartons ?? r.recommended_order)}.</p><Link className="mt-2 inline-block text-sm font-black text-blue-700 underline" href="/dashboard/inventory">לפתיחת המלאי והמלצות הרכש</Link></div></div></div>) : <Empty text="אין מספיק ספירות מלאי תקינות בתקופה כדי להציג קצב צריכה מהימן."/>}
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 dark:border-amber-900 dark:bg-amber-950/20"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 shrink-0 text-amber-700" size={19}/><div><p className="font-black">פריטים בסיכון או ללא נתוני תכנון</p><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{riskCount ? `${riskCount} פריטים דורשים בדיקה או השלמת נתונים.` : "לא זוהו פריטים בסיכון לפי נתוני התכנון שנטענו."}</p><Link href="/dashboard/inventory" className="mt-2 inline-block text-sm font-black text-amber-800 underline">בדיקת מלאי</Link></div></div></div>
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><div className="flex items-start gap-3"><Truck className="mt-0.5 shrink-0 text-slate-600" size={19}/><div><p className="font-black">ביצועי ספקים</p><p className="mt-1 text-sm text-slate-500">נתוני איחורי אספקה בפועל אינם זמינים כרגע במקור הנתונים המחובר; לא נציג זמן איחור משוער כעובדה.</p><Link href="/dashboard/suppliers" className="mt-2 inline-block text-sm font-black underline">לניהול ספקים</Link></div></div></div>
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><div className="flex items-start gap-3"><ShoppingCart className="mt-0.5 shrink-0 text-slate-600" size={19}/><div><p className="font-black">הזדמנויות לחיסכון</p><p className="mt-1 text-sm text-slate-500">כדאי לבדוק פערי מחיר במוצרים עם כמה הצעות ספק; חיסכון כספי בפועל תלוי בכמות ובהשוואת יחידות זהות.</p><Link href="/dashboard/price-intelligence/overview" className="mt-2 inline-block text-sm font-black underline">פתיחת השוואת מחירים</Link></div></div></div>
      </div>}
    </Panel>
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel title="מגמת הוצאות רכש" subtitle="הזמנות שאושרו, נשלחו או הושלמו לפי חודש יצירת ההזמנה">
        <div className="space-y-3">{monthlySpend.map(m=><div key={m.key} className="grid grid-cols-[42px_1fr_100px] items-center gap-3 text-sm"><span className="font-bold text-slate-500">{m.label}</span><div className="h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-indigo-500" style={{width:`${m.amount/maxSpend*100}%`}}/></div><span className="text-left font-bold tabular-nums">{money(m.amount)}</span></div>)}</div>
        <p className="mt-4 text-xs text-slate-500">זהו סיכום רכש לפי סטטוס ותאריך יצירה, לא תזרים תשלומים חשבונאי.</p>
      </Panel>
      <Panel title="שווי מלאי לפי קטגוריה" subtitle="שווי מחושב לפי מחיר המוצר והמלאי הנוכחי">
        {categoryStats.length ? <div className="space-y-3">{categoryStats.map(c=><div key={c.name}><div className="mb-1 flex items-center justify-between gap-3 text-sm"><span className="truncate font-bold">{c.name}</span><span className="shrink-0 text-slate-500">{money(c.value)}</span></div><div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-sky-500" style={{width:`${c.value/maxCategory*100}%`}}/></div></div>)}</div> : <Empty text="אין נתוני קטגוריה להצגה."/>}
      </Panel>
    </div>
    <Panel title="טבלת מלאי, צריכה והמלצת רכש" subtitle="סינון משותף לטבלה ולמדדי הסיכון">
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs font-bold text-slate-600">ספק<select value={supplier} onChange={e=>setSupplier(e.target.value)} className="mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="all">כל הספקים</option>{suppliers.map(s=><option key={s.id} value={String(s.id)}>{s.name}</option>)}</select></label>
        <label className="text-xs font-bold text-slate-600">קטגוריה<select value={category} onChange={e=>setCategory(e.target.value)} className="mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="all">כל הקטגוריות</option>{categories.map(c=><option key={c}>{c}</option>)}</select></label>
        <label className="text-xs font-bold text-slate-600">סטטוס<select value={risk} onChange={e=>setRisk(e.target.value)} className="mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="all">כל המצבים</option><option value="urgent">דחוף</option><option value="reorder">נדרשת הזמנה</option><option value="healthy">תקין</option><option value="insufficient_data">חסרים נתונים</option></select></label>
        <div className="flex items-end text-sm text-slate-500">מציג {visibleProducts.length} מוצרים בקטלוג המסונן</div>
      </div>
      {loading ? <Empty text="טוען את טבלת הדוח…"/> : <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800"><table className="w-full min-w-[980px] text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr>{["מוצר","ספק","קטגוריה","מלאי נוכחי","צריכה יומית","צריכה שבועית","כיסוי בימים","הזמנה מומלצת","סטטוס","פעולה"].map(h=><th key={h} className="whitespace-nowrap px-3 py-3 font-bold">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{visibleProducts.filter(p=>{const rec=recommendationMap.get(p.id);return risk==="all" ? true : rec?.status===risk;}).map(p=>{const rec=recommendationMap.get(p.id);const status=rec?.status==="urgent"?"דחוף":rec?.status==="reorder"?"הזמנה":rec?.status==="healthy"?"תקין":"חסר מידע";return <tr key={p.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-900/60"><td className="max-w-[220px] px-3 py-3 font-bold">{p.name}</td><td className="px-3 py-3 text-slate-500">{suppliers.find(s=>s.id===p.supplier_id)?.name||"—"}</td><td className="px-3 py-3 text-slate-500">{p.category||"—"}</td><td className="px-3 py-3 tabular-nums">{qty(Number(p.current_stock??0))} {p.stock_unit||p.unit||""}</td><td className="px-3 py-3 tabular-nums">{rec?.average_daily_usage_cartons!=null?`${qty(rec.average_daily_usage_cartons)} קרטון`:rec?.data_ready?qty(rec.average_daily_usage):"—"}</td><td className="px-3 py-3 tabular-nums">{rec?.weekly_usage_cartons!=null?`${qty(rec.weekly_usage_cartons)} קרטון`:rec?.data_ready?qty(rec.average_daily_usage*7):"—"}</td><td className="px-3 py-3 tabular-nums">{rec?.coverage_days==null?"—":qty(rec.coverage_days)}</td><td className="px-3 py-3 font-black tabular-nums">{rec?.recommended_order_cartons!=null?`${qty(rec.recommended_order_cartons)} קרטון`:rec?.data_ready?qty(rec.recommended_order):"—"}</td><td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-xs font-bold ${rec?.status==="urgent"?"bg-red-100 text-red-700":rec?.status==="reorder"?"bg-amber-100 text-amber-800":rec?.status==="healthy"?"bg-emerald-100 text-emerald-700":"bg-slate-100 text-slate-600"}`}>{status}</span></td><td className="px-3 py-3"><Link href="/dashboard/inventory" className="whitespace-nowrap font-black text-indigo-700 underline">פתח מלאי</Link></td></tr>;})}</tbody></table></div>}
    </Panel>
    <footer className="flex items-start gap-2 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-500 dark:bg-slate-900"><CalendarDays size={16} className="mt-0.5 shrink-0"/> דוח זה משתמש במקורות הקיימים במערכת. השוואת שווי מלאי לחודש קודם, ניצולת תקציב, השוואת צריכה שבועית לממוצע חודשי, מלאי מת ללא תנועה לאורך 60 יום ואיחורי ספקים יופיעו רק לאחר חיבור היסטוריית מלאי/תקציב/אספקות מתאימה — לא מוצגים מספרים מומצאים.</footer>
  </main>;
}
