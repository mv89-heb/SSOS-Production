"use client";

import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  Award,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  PackageSearch,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { catalogService } from "@/services/catalog-service";
import { priceIntelligenceService } from "@/services/price-intelligence-service";

const money = (value: number | null | undefined, currency = "ILS") => {
  const amount = Number(value ?? 0);
  try {
    return new Intl.NumberFormat("he-IL", {
      style: "currency",
      currency: currency || "ILS",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency || "ILS"}`;
  }
};

const number = (value: number | null | undefined) =>
  new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(Number(value ?? 0));

function StatCard({ label, value, hint, icon }: { label: string; value: string; hint: string; icon: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="border-b border-slate-100 p-5 dark:border-slate-800">
        <h2 className="font-black text-slate-900 dark:text-white">{title}</h2>
        {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

export default function ProcurementIntelligencePage() {
  const summary = useQuery({
    queryKey: ["procurement-intelligence", "summary"],
    queryFn: () => priceIntelligenceService.getPortfolioSummary(10),
    retry: 1,
  });
  const suppliers = useQuery({
    queryKey: ["procurement-intelligence", "suppliers"],
    queryFn: () => priceIntelligenceService.getSupplierScores(8),
    retry: 1,
  });
  const products = useQuery({
    queryKey: ["procurement-intelligence", "catalog-products"],
    queryFn: () => catalogService.listProducts(undefined, true),
    retry: 1,
  });

  const [briefing, setBriefing] = useState<Awaited<ReturnType<typeof priceIntelligenceService.getAiBriefing>> | null>(null);
  const [aiError, setAiError] = useState<string>();
  const [aiLoading, setAiLoading] = useState(false);

  const refresh = () => {
    void summary.refetch();
    void suppliers.refetch();
    void products.refetch();
  };

  const runBriefing = async () => {
    setAiLoading(true);
    setAiError(undefined);
    try {
      setBriefing(await priceIntelligenceService.getAiBriefing());
    } catch (error) {
      setAiError(error instanceof Error ? error.message : "לא ניתן להפעיל את Gemini כרגע.");
    } finally {
      setAiLoading(false);
    }
  };

  const data = summary.data;
  const supplierData = suppliers.data;
  const productRows = products.data ?? [];
  const loading = summary.isLoading || suppliers.isLoading || products.isLoading;

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-600">
              <BarChart3 size={18} />
              <span className="text-sm font-bold">Procurement Intelligence Center</span>
            </div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white">מרכז מודיעין רכש</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-500">
              מסך ניהולי אמיתי על בסיס הקטלוג הקיים: מוצרים, מחירים, חלופות, ספקים, הזדמנויות חיסכון ושינויי מחיר.
              אין כאן נתונים מומצאים — רק נתוני הרכש של הארגון.
            </p>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold shadow-sm hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            רענן נתונים
          </button>
        </div>
      </header>

      {(summary.isError || suppliers.isError || products.isError) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
          <div className="font-bold">חלק מנתוני המודיעין לא נטענו</div>
          <div className="mt-1">הקטלוג והנתונים הזמינים עדיין מוצגים. לחץ על רענן נתונים לאחר שהשרת זמין.</div>
        </div>
      )}

      {data ? (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="חיסכון פוטנציאלי"
            value={money(data.potential_savings)}
            hint={`${number(data.potential_savings_percent)}% מהמחיר הנוכחי ליחידה`}
            icon={<ArrowDown className="text-emerald-500" size={18} />}
          />
          <StatCard
            label="מוצרים עם הזדמנות"
            value={number(data.opportunity_products)}
            hint={`מתוך ${number(data.products_analyzed)} מוצרים שנותחו`}
            icon={<Sparkles className="text-violet-500" size={18} />}
          />
          <StatCard
            label="חלופות ברות-השוואה"
            value={number(data.products_with_comparable_alternatives)}
            hint="לפחות ספק חלופי אחד באותה יחידת השוואה ומטבע"
            icon={<CheckCircle2 className="text-blue-500" size={18} />}
          />
          <StatCard
            label="עלות נוכחית → מיטבית"
            value={`${money(data.current_unit_total)} → ${money(data.best_unit_total)}`}
            hint="סכום מחירי יחידה להשוואה"
            icon={<TrendingUp className="text-indigo-500" size={18} />}
          />
        </section>
      ) : (
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="מוצרים בקטלוג" value={number(productRows.length)} hint="נתוני הקטלוג החיים של הארגון" icon={<PackageSearch className="text-indigo-500" size={18} />} />
          <StatCard label="מנוע מודיעין" value="פעיל" hint="מחירי ספקים והשוואות" icon={<BarChart3 className="text-emerald-500" size={18} />} />
          <StatCard label="ספקים בדירוג" value={number(supplierData?.suppliers?.length)} hint="על בסיס תחרותיות מחיר" icon={<Award className="text-amber-500" size={18} />} />
          <StatCard label="סטטוס" value={loading ? "טוען…" : "ממתין לנתונים"} hint="רענן כדי לנסות שוב" icon={<RefreshCw className="text-slate-400" size={18} />} />
        </section>
      )}

      <Section title="קטלוג רכש חי" hint={`${number(productRows.length)} מוצרים פעילים — כדי שהמסך לא יהיה ריק גם כשאין עדיין השוואות מחיר.`}>
        {productRows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                <tr>
                  <th className="px-5 py-3">מוצר</th>
                  <th className="px-5 py-3">קטגוריה</th>
                  <th className="px-5 py-3">מחיר נוכחי</th>
                  <th className="px-5 py-3">יחידה</th>
                  <th className="px-5 py-3">מלאי</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {productRows.slice(0, 25).map((product) => (
                  <tr key={product.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50">
                    <td className="px-5 py-4 font-semibold text-slate-900 dark:text-white">
                      {product.name}
                      <div className="text-xs font-normal text-slate-400">{product.sku || "ללא מק״ט"}</div>
                    </td>
                    <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{product.category || "ללא קטגוריה"}</td>
                    <td className="px-5 py-4 font-black text-indigo-700 dark:text-indigo-300">{money(product.current_price, product.currency || "ILS")}</td>
                    <td className="px-5 py-4">{product.unit || "יחידה"}</td>
                    <td className="px-5 py-4">{product.current_stock == null ? "—" : number(product.current_stock)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center">
            <PackageSearch className="mx-auto text-slate-300" size={38} />
            <div className="mt-3 font-bold text-slate-700 dark:text-slate-200">אין מוצרים פעילים בקטלוג</div>
            <div className="mt-1 text-sm text-slate-500">ייבא מחירון או הוסף מוצרים במסך הקטלוג כדי להזין את מרכז המודיעין.</div>
          </div>
        )}
      </Section>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <Section title="הזדמנויות חיסכון מובילות" hint="השוואה דטרמיניסטית לפי יחידת בסיס ומטבע; ללא המצאת נתונים.">
          {data?.top_opportunities?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-right text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                  <tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">ספק נוכחי</th><th className="px-5 py-3">ספק זול יותר</th><th className="px-5 py-3">חיסכון</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {data.top_opportunities.map((row) => (
                    <tr key={row.product_id}>
                      <td className="px-5 py-4 font-semibold">{row.product_name}<div className="text-xs text-slate-400">{row.sku || "ללא מק״ט"}</div></td>
                      <td className="px-5 py-4">{row.current_supplier || "—"}</td>
                      <td className="px-5 py-4 font-semibold text-emerald-700 dark:text-emerald-300">{row.best_supplier || "—"}</td>
                      <td className="px-5 py-4 font-black text-emerald-700 dark:text-emerald-300">{money(row.savings_per_unit, row.currency)}<div className="text-xs font-normal">{number(row.savings_percent)}%</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-slate-500">אין כרגע הזדמנויות חיסכון שניתנות להשוואה. זה לא אומר שהקטלוג ריק.</div>
          )}
        </Section>

        <Section title="דירוג ספקים לפי מחיר" hint="הציון משקף כיסוי בקטלוג וניצחונות במחיר בלבד — לא איכות או שירות.">
          {supplierData?.suppliers?.length ? (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {supplierData.suppliers.map((supplier, index) => (
                <div key={supplier.supplier_id} className="flex items-center gap-3 p-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sm font-black dark:bg-slate-900">{index + 1}</div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold">{supplier.supplier_name || `ספק #${supplier.supplier_id}`}</div>
                    <div className="mt-1 text-xs text-slate-400">כיסוי {number(supplier.coverage_percent)}% · ניצחונות {supplier.wins}/{supplier.participation}</div>
                  </div>
                  <div className="text-left"><div className="font-black text-indigo-600">{number(supplier.score)}</div><div className="text-[10px] text-slate-400">ציון</div></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-sm text-slate-500">אין עדיין מספיק הצעות ספקים להשוואה.</div>
          )}
        </Section>
      </div>

      <Section title="שינויי מחיר אחרונים" hint="היסטוריית מחירים שנרשמה במערכת.">
        {data?.recent_changes?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                <tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר קודם</th><th className="px-5 py-3">מחיר חדש</th><th className="px-5 py-3">שינוי</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {data.recent_changes.map((row) => (
                  <tr key={row.id}>
                    <td className="px-5 py-4 font-semibold">#{row.product_id}</td>
                    <td className="px-5 py-4">{row.supplier_name || `ספק #${row.supplier_id}`}</td>
                    <td className="px-5 py-4">{row.old_price == null ? "—" : money(row.old_price, row.currency)}</td>
                    <td className="px-5 py-4 font-bold">{money(row.new_price, row.currency)}</td>
                    <td className={`px-5 py-4 font-black ${(row.change_percent ?? 0) > 0 ? "text-red-600" : "text-emerald-600"}`}>{row.change_percent == null ? "—" : `${number(row.change_percent)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-sm text-slate-500">אין עדיין היסטוריית שינויי מחיר.</div>
        )}
      </Section>

      <section className="overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-indigo-50 shadow-sm dark:border-violet-900 dark:from-violet-950/30 dark:via-slate-950 dark:to-indigo-950/20">
        <div className="flex flex-col gap-4 border-b border-violet-100 p-5 dark:border-violet-900/60 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-xl bg-violet-600 p-2 text-white"><BrainCircuit size={20} /></div><div><h2 className="font-black text-violet-950 dark:text-violet-100">Gemini Executive Briefing</h2><p className="mt-1 text-sm text-violet-900/70 dark:text-violet-200/70">Gemini מפרש את הנתונים הקיימים בלבד ואינו משנה אותם.</p></div></div>
          <button type="button" onClick={runBriefing} disabled={aiLoading || !data} className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-60"><Sparkles size={16} />{aiLoading ? "Gemini מנתח..." : "הפק סיכום מנהלים"}</button>
        </div>
        <div className="p-5">
          {aiError && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">{aiError}</div>}
          {!briefing && !aiError && <div className="text-sm text-slate-500">הפקת הסיכום תנתח את ההזדמנויות, הסיכונים והפעולות על בסיס נתוני המסך.</div>}
          {briefing && <div className="grid gap-5 md:grid-cols-3"><div><div className="mb-2 font-bold text-emerald-700">הזדמנויות</div><ul className="space-y-2 text-sm">{briefing.briefing.highlights.map((x, i) => <li key={`h-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-amber-700">סיכונים</div><ul className="space-y-2 text-sm">{briefing.briefing.risks.map((x, i) => <li key={`r-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-indigo-700">פעולות</div><ul className="space-y-2 text-sm">{briefing.briefing.actions.map((x, i) => <li key={`a-${i}`}>→ {x}</li>)}</ul></div></div>}
        </div>
      </section>

      <div className="flex items-center gap-2 text-xs text-slate-400"><AlertTriangle size={14} /> הנתונים מוצגים לפי הרשאות הארגון וה־tenant המחובר.</div>
    </div>
  );
}
