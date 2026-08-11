"use client";

import { useState } from "react";
import { BookOpen, CheckCircle2, ChevronDown, HelpCircle, MessageCircle, Package, Settings, ShoppingCart, Upload, Users } from "lucide-react";

const sections = [
  { id: "start", title: "איך מתחילים?", icon: BookOpen, text: "העבודה המומלצת היא לבחור או להוסיף ספק, לוודא שהמוצרים קיימים בקטלוג, ליצור הזמנה, לבדוק את הפריטים והכמויות ולבסוף לשלוח אותה לספק." },
  { id: "suppliers", title: "ניהול ספקים", icon: Users, text: "במסך הספקים אפשר להוסיף ספקים, לעדכן פרטי קשר ולנהל את מצב הפעילות שלהם. מומלץ לשמור מספר WhatsApp של הספק כדי להקל על שליחת הזמנות." },
  { id: "products", title: "קטלוג מוצרים", icon: Package, text: "המוצרים מקושרים לספקים וכוללים את פרטי המוצר הדרושים להזמנה. לפני יצירת הזמנה כדאי לוודא שהמוצר פעיל ושמו וכמותו נכונים." },
  { id: "orders", title: "יצירת הזמנה", icon: ShoppingCart, text: "בחר ספק, הוסף את המוצרים והכמויות הרצויים, בדוק את ההזמנה ושמור אותה. ניתן לערוך את ההזמנה לפי ההרשאות שלך לפני שליחתה." },
  { id: "whatsapp", title: "שליחה ב־WhatsApp", icon: MessageCircle, text: "במסך ההזמנה בחר תבנית, בדוק את ההודעה ולחץ על פתיחת WhatsApp. ההודעה כוללת את שם הארגון, מספר ההזמנה, הפריטים והכמויות — ללא מחירים." },
  { id: "imports", title: "ייבוא מחירונים", icon: Upload, text: "העלה את הקובץ דרך מסך הייבוא ובדוק את תוצאות הניתוח והמיפוי לפני אישור. היסטוריית ייבואים נשמרת לצורך מעקב ובקרה." },
  { id: "admin", title: "מרכז מנהל מערכת", icon: Settings, text: "מנהלי מערכת יכולים לנהל משתמשים, ספקים, מוצרים והזמנות, לבצע פעולות עריכה והשבתה ולבצע מחיקות בהתאם להגבלות האבטחה. פעולות ניהול משמעותיות מתועדות ב־Audit." },
];

export default function HelpPage() {
  const [open, setOpen] = useState("start");
  return (
    <main dir="rtl" className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="rounded-3xl bg-gradient-to-br from-indigo-700 to-violet-700 p-6 text-white shadow-xl sm:p-8">
        <div className="flex items-start gap-4"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/15"><HelpCircle className="h-6 w-6" /></div><div><p className="text-sm font-bold text-indigo-100">ישיבת אוהבי ירושלים - ראשית</p><h1 className="mt-1 text-2xl font-black sm:text-3xl">מרכז עזרה</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">הסברים קצרים שיעזרו לך לעבוד נכון עם ספקים, מוצרים, הזמנות, ייבואים ושליחה ב־WhatsApp.</p></div></div>
      </header>
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-6">
        <div className="mb-4 flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><h2 className="font-black text-slate-900 dark:text-white">מסלול עבודה מומלץ</h2></div>
        <div className="grid gap-2 sm:grid-cols-4">{["1. ספק", "2. מוצרים", "3. הזמנה", "4. שליחה ב־WhatsApp"].map((item, i) => <div key={item} className="rounded-xl bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700 dark:bg-slate-900 dark:text-slate-200"><span className="me-2 text-indigo-600">{i + 1}</span>{item.replace(/^\d+\. /, "")}</div>)}</div>
      </section>
      <section className="space-y-2">
        {sections.map(({ id, title, icon: Icon, text }) => { const active = open === id; return <div key={id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"><button type="button" onClick={() => setOpen(active ? "" : id)} className="flex w-full items-center gap-3 px-4 py-4 text-right hover:bg-slate-50 dark:hover:bg-slate-900"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"><Icon className="h-4 w-4" /></span><span className="flex-1 font-black text-slate-900 dark:text-white">{title}</span><ChevronDown className={`h-5 w-5 text-slate-400 transition-transform ${active ? "rotate-180" : ""}`} /></button>{active && <div className="border-t border-slate-100 px-4 pb-5 pt-4 text-sm leading-7 text-slate-600 dark:border-slate-800 dark:text-slate-300">{text}</div>}</div>; })}
      </section>
    </main>
  );
}
