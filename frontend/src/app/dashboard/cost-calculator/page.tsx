"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Calculator, CircleDollarSign, Plus, RotateCcw, Trash2, Scale, Package, ChefHat } from "lucide-react";

type Mode = "weight" | "unit" | "recipe";
type Ingredient = { id: number; name: string; packagePrice: string; packageQty: string; recipeQty: string; unit: "g" | "kg" | "ml" | "l" | "unit" };
const initialIngredients: Ingredient[] = [
  { id: 1, name: "מרכיב לדוגמה", packagePrice: "12", packageQty: "1000", recipeQty: "150", unit: "g" },
];
const money = (value: number) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 2 }).format(Number.isFinite(value) ? value : 0);
const numberValue = (value: string) => Math.max(0, Number(value) || 0);

export default function CostCalculatorPage() {
  const [mode, setMode] = useState<Mode>("recipe");
  const [pricePerKg, setPricePerKg] = useState("24");
  const [weight, setWeight] = useState("250");
  const [weightUnit, setWeightUnit] = useState<"g" | "kg">("g");
  const [unitPrice, setUnitPrice] = useState("4.5");
  const [quantity, setQuantity] = useState("3");
  const [packagePrice, setPackagePrice] = useState("36");
  const [unitsPerPackage, setUnitsPerPackage] = useState("12");
  const [ingredients, setIngredients] = useState<Ingredient[]>(initialIngredients);
  const [waste, setWaste] = useState("5");
  const [multiplier, setMultiplier] = useState("3");
  const [targetSellingPrice, setTargetSellingPrice] = useState("");
  const [nextId, setNextId] = useState(2);

  const results = useMemo(() => {
    const rawRecipeCost = ingredients.reduce((sum, item) => {
      const packQty = numberValue(item.packageQty);
      const recipeQty = numberValue(item.recipeQty);
      if (!packQty || !recipeQty) return sum;
      return sum + numberValue(item.packagePrice) * recipeQty / packQty;
    }, 0);
    const wasteRate = Math.min(99.99, numberValue(waste)) / 100;
    const costWithWaste = rawRecipeCost / (1 - wasteRate);
    const suggested = costWithWaste * numberValue(multiplier);
    const sell = targetSellingPrice.trim() === "" ? suggested : numberValue(targetSellingPrice);
    return {
      weightCost: numberValue(pricePerKg) * numberValue(weight) / (weightUnit === "g" ? 1000 : 1),
      unitCost: (numberValue(packagePrice) / (numberValue(unitsPerPackage) || 1)) * numberValue(quantity),
      rawRecipeCost, costWithWaste, suggested,
      profit: sell - costWithWaste,
      margin: sell > 0 ? (sell - costWithWaste) / sell * 100 : 0,
    };
  }, [pricePerKg, weight, weightUnit, packagePrice, unitsPerPackage, quantity, ingredients, waste, multiplier, targetSellingPrice]);

  const updateIngredient = (id: number, key: keyof Ingredient, value: string) =>
    setIngredients((items) => items.map((item) => item.id === id ? { ...item, [key]: value } : item));
  const addIngredient = () => {
    setIngredients((items) => [...items, { id: nextId, name: "", packagePrice: "", packageQty: "1000", recipeQty: "", unit: "g" }]);
    setNextId((id) => id + 1);
  };
  const reset = () => {
    setMode("recipe"); setPricePerKg("24"); setWeight("250"); setWeightUnit("g");
    setUnitPrice("4.5"); setQuantity("3"); setPackagePrice("36"); setUnitsPerPackage("12");
    setIngredients(initialIngredients); setWaste("5"); setMultiplier("3"); setTargetSellingPrice(""); setNextId(2);
  };

  const tabs: { id: Mode; title: string; desc: string; Icon: typeof Scale }[] = [
    { id: "weight", title: "לפי משקל", desc: "מחיר לק״ג ומשקל בפועל", Icon: Scale },
    { id: "unit", title: "לפי יחידה / אריזה", desc: "מחיר ליחידה או חלוקה מאריזה", Icon: Package },
    { id: "recipe", title: "עלות מתכון ומנה", desc: "מרכיבים, פחת ורווח צפוי", Icon: ChefHat },
  ];
  return (
    <div dir="rtl" className="mx-auto max-w-6xl space-y-6 text-slate-900 dark:text-slate-100">
      <header className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-slate-950 via-indigo-950 to-blue-900 p-6 text-white shadow-xl sm:p-8">
        <div className="absolute -left-10 -top-16 h-48 w-48 rounded-full bg-cyan-400/15 blur-3xl" aria-hidden="true" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-bold text-blue-100"><Calculator className="h-4 w-4" /> כלי חישוב לתמחור</div>
            <h1 className="text-2xl font-black tracking-tight sm:text-3xl">מחשבון עלויות ותמחור</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-blue-100 sm:text-base">חשבו עלות לפי משקל, יחידה או מתכון — עם פחת, מחיר מכירה מומלץ ורווח צפוי. החישובים זמניים ואינם נשמרים.</p>
          </div>
          <button onClick={reset} className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm font-bold transition hover:bg-white/15"><RotateCcw className="h-4 w-4" /> איפוס חישוב</button>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        {tabs.map(({ id, title, desc, Icon }) => <button key={id} onClick={() => setMode(id)} aria-pressed={mode === id} className={`rounded-2xl border p-4 text-right transition ${mode === id ? "border-indigo-500 bg-indigo-50 shadow-md ring-1 ring-indigo-500/20 dark:bg-indigo-950/40" : "border-slate-200 bg-white hover:border-indigo-200 dark:border-slate-800 dark:bg-slate-900"}`}>
          <div className="flex items-center gap-3"><span className={`flex h-10 w-10 items-center justify-center rounded-xl ${mode === id ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}><Icon className="h-5 w-5" /></span><span className="font-extrabold">{title}</span></div>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{desc}</p>
        </button>)}
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-6">
          {mode === "weight" && <div className="space-y-4">
            <h2 className="text-lg font-extrabold">חישוב לפי משקל</h2>
            <Field label="מחיר לקילוגרם (₪)" value={pricePerKg} onChange={setPricePerKg} />
            <div className="grid gap-4 sm:grid-cols-2"><Field label="משקל נדרש" value={weight} onChange={setWeight} /><SelectField label="יחידת משקל" value={weightUnit} onChange={(v) => setWeightUnit(v as "g" | "kg")} options={[["g", "גרם"], ["kg", "קילוגרם"]]} /></div>
            <Formula>עלות = מחיר לק״ג × משקל בגרמים ÷ 1,000</Formula>
          </div>}
          {mode === "unit" && <div className="space-y-4">
            <h2 className="text-lg font-extrabold">חישוב לפי יחידה או אריזה</h2>
            <div className="grid gap-4 sm:grid-cols-2"><Field label="מחיר אריזה (₪)" value={packagePrice} onChange={setPackagePrice} /><Field label="יחידות באריזה" value={unitsPerPackage} onChange={setUnitsPerPackage} /><Field label="כמות נדרשת" value={quantity} onChange={setQuantity} /><Field label="מחיר יחידה ידני (לחלופה)" value={unitPrice} onChange={setUnitPrice} /></div>
            <Formula>עלות = (מחיר אריזה ÷ מספר יחידות באריזה) × כמות נדרשת</Formula>
            <p className="text-xs text-slate-500">החישוב משתמש במחיר האריזה ובמספר היחידות. שדה מחיר היחידה הידני הוא לעזר ואינו משפיע על התוצאה כרגע.</p>
          </div>}
          {mode === "recipe" && <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-extrabold">מרכיבי המתכון</h2><p className="mt-1 text-sm text-slate-500">הזינו מחיר אריזה, כמות באריזה והכמות הנדרשת למנה.</p></div><button onClick={addIngredient} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-bold text-white hover:bg-indigo-700"><Plus className="h-4 w-4" /> הוספת מרכיב</button></div>
            <div className="space-y-3">
              {ingredients.map((item, index) => <div key={item.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                <div className="mb-3 flex items-center justify-between"><span className="text-sm font-extrabold">מרכיב {index + 1}</span><button onClick={() => setIngredients((items) => items.filter((i) => i.id !== item.id))} aria-label={`הסר מרכיב ${index + 1}`} className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button></div>
                <label className="mb-3 block text-sm font-semibold">שם המרכיב<input value={item.name} onChange={(e) => updateIngredient(item.id, "name", e.target.value)} placeholder="למשל: קמח" className={inputClass} /></label>
                <div className="grid gap-3 sm:grid-cols-3"><Field label="מחיר אריזה (₪)" value={item.packagePrice} onChange={(v) => updateIngredient(item.id, "packagePrice", v)} /><Field label={`כמות באריזה (${item.unit})`} value={item.packageQty} onChange={(v) => updateIngredient(item.id, "packageQty", v)} /><Field label={`כמות למנה (${item.unit})`} value={item.recipeQty} onChange={(v) => updateIngredient(item.id, "recipeQty", v)} /></div>
                <p className="mt-2 text-xs text-slate-500">עלות מרכיב: {money(numberValue(item.packagePrice) * numberValue(item.recipeQty) / (numberValue(item.packageQty) || 1))}</p>
              </div>)}
              {ingredients.length === 0 && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500 dark:bg-slate-800">הוסיפו לפחות מרכיב אחד לחישוב עלות המתכון.</p>}
            </div>
            <div className="grid gap-4 sm:grid-cols-2"><Field label="פחת (%)" value={waste} onChange={setWaste} /><Field label="מכפיל תמחור" value={multiplier} onChange={setMultiplier} /></div>
            <Formula>עלות לאחר פחת = עלות חומרי גלם ÷ (1 − שיעור הפחת)</Formula>
            <p className="text-xs leading-5 text-slate-500">המכפיל קובע את מחיר המכירה המומלץ ביחס לעלות לאחר פחת; מכפיל 3 אינו רווח של 300%. החישוב אינו כולל עבודה, אנרגיה, אריזה והוצאות קבועות.</p>
          </div>}
        </section>

        <aside className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-4 flex items-center gap-2"><CircleDollarSign className="h-5 w-5 text-indigo-600" /><h2 className="font-extrabold">תוצאות החישוב</h2></div>
            {mode === "weight" && <Result label="עלות המשקל המבוקש" value={money(results.weightCost)} />}
            {mode === "unit" && <><Result label="מחיר ליחידה" value={money(numberValue(packagePrice) / (numberValue(unitsPerPackage) || 1))} /><Result label={`עלות ${numberValue(quantity)} יחידות`} value={money(results.unitCost)} /></>}
            {mode === "recipe" && <>
              <Result label="עלות חומרי גלם למנה" value={money(results.rawRecipeCost)} />
              <Result label="עלות למנה כולל פחת" value={money(results.costWithWaste)} />
              <div className="my-4 border-t border-slate-100 dark:border-slate-800" />
              <Result label="מחיר מכירה מומלץ" value={money(results.suggested)} highlight />
              <label className="mt-4 block text-sm font-semibold">בדיקת מחיר מכירה בפועל (₪)<input type="number" min="0" step="0.01" value={targetSellingPrice} onChange={(e) => setTargetSellingPrice(e.target.value)} placeholder="ברירת מחדל: המחיר המומלץ" className={inputClass} /></label>
              <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-800"><p className="text-sm text-slate-500">רווח צפוי למנה</p><p className={`mt-1 text-2xl font-black ${results.profit < 0 ? "text-rose-600" : "text-emerald-600"}`}>{money(results.profit)}</p><p className="mt-1 text-xs text-slate-500">שיעור רווח ממחיר המכירה: {results.margin.toFixed(1)}%</p></div>
            </>}
          </div>
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm leading-6 text-blue-950 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100">
            <p className="font-extrabold">לתשומת לב</p><p className="mt-1">זהו מחשבון זמני בלבד: אין שמירה למסד הנתונים, אין שינוי במחירי ספקים ואין כתיבה להיסטוריית הרכש.</p>
            <p className="mt-2">כדי למנוע מחיר שגוי, יש להזין את המחיר העדכני מתוך מסך הקטלוג. חיבור לבחירת מוצר ומחיר ספק קיים יתווסף רק לאחר אימות ממשק הנתונים הקיים.</p>
          </div>
          <Link href="/dashboard/catalog" className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900"><span>חזרה לקטלוג ומחירים</span><ArrowLeft className="h-4 w-4" /></Link>
          <Link href="/dashboard/inventory" className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900"><span>מעבר למלאי</span><ArrowLeft className="h-4 w-4" /></Link>
        </aside>
      </div>
      <p className="text-center text-xs text-slate-400">כל החישובים מתבצעים בדפדפן ואינם נשמרים לאחר סגירת/רענון העמוד.</p>
    </div>
  );
}

const inputClass = "mt-1.5 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/15 dark:border-slate-700 dark:bg-slate-950";
function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-semibold">{label}<input type="number" min="0" step="any" value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} /></label>;
}
function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label className="block text-sm font-semibold">{label}<select value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>{options.map(([v, name]) => <option key={v} value={v}>{name}</option>)}</select></label>;
}
function Formula({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/60 p-3 text-sm font-semibold text-indigo-950 dark:border-indigo-900 dark:bg-indigo-950/30 dark:text-indigo-100">{children}</div>;
}
function Result({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return <div className={`flex items-center justify-between gap-3 rounded-xl p-3 ${highlight ? "bg-indigo-50 dark:bg-indigo-950/40" : "border-b border-slate-100 dark:border-slate-800"}`}><span className="text-sm text-slate-500 dark:text-slate-400">{label}</span><span className={`text-lg font-black tabular-nums ${highlight ? "text-indigo-700 dark:text-indigo-300" : ""}`}>{value}</span></div>;
}
