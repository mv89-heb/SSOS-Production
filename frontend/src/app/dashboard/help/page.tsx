"use client";

import { useState } from "react";
import Link from "next/link";
import {
  BookOpen, CheckCircle2, ChevronDown, HelpCircle, MessageCircle, Package,
  Settings, ShoppingCart, Upload, Users, BarChart3, BrainCircuit, FileSearch,
  Warehouse, CalendarDays, History, ShieldCheck, Lightbulb, ArrowLeft,
} from "lucide-react";

const sections = [
  {
    id: "start",
    title: "איך מתחילים לעבוד במערכת?",
    icon: BookOpen,
    intro: "מומלץ להתקדם בסדר הבא: להגדיר ספקים ומוצרים, לעדכן מחירים, לתעד מלאי לפי הצורך, ליצור הזמנת רכש ולעקוב אחר הפעולות.",
    steps: [
      "בדוק במסך ספקים שהספק קיים ופרטי הקשר שלו מעודכנים.",
      "במוצרים ומחירים, ודא שהמוצר קיים ושהוא משויך להצעות הספק המתאימות. שמות שונים לאותו מוצר אצל ספקים שונים צריכים להיבדק לפני איחוד.",
      "בדוק את המחירים ותאריך העדכון לפני קבלת החלטה או יצירת הזמנה.",
      "צור הזמנת רכש, בדוק את הספק, הפריטים והכמויות, ורק אז המשך לשליחה או לטיפול הבא.",
      "היעזר במסמכים וקליטה, בתמונת מצב רכש ובהיסטוריית הפעולות כדי לבדוק את מקור הנתונים ואת מה שכבר בוצע.",
    ],
    tips: ["אם נתון חסר או נראה חריג, בדוק את המקור ותקן אותו במסך המתאים במקום להסתמך על הערכה בלבד."],
  },
  {
    id: "dashboard",
    title: "לוח בקרה",
    icon: BarChart3,
    intro: "לוח הבקרה הוא נקודת הפתיחה לקבלת תמונת מצב מהירה של פעילות הרכש.",
    steps: [
      "התחל בלוח הבקרה כדי לזהות נתונים או פעולות שדורשים תשומת לב.",
      "פתח את המסך הרלוונטי להמשך טיפול — הזמנות, ספקים, קטלוג, מלאי או ניתוח רכש.",
      "כאשר נתון בלוח דורש בדיקה, אמת אותו במסך המקור לפני קבלת החלטה.",
    ],
    link: { href: "/dashboard", label: "פתיחת לוח הבקרה" },
  },
  {
    id: "suppliers",
    title: "ספקים",
    icon: Users,
    intro: "מסך הספקים מרכז את פרטי הספקים המשמשים בתהליכי הרכש.",
    steps: [
      "חפש ספק לפי שם או לפי מסנני החיפוש הזמינים במסך.",
      "הוסף ספק חדש או עדכן פרטים קיימים בהתאם להרשאות שלך.",
      "בדוק ששם הספק ופרטי הקשר מדויקים כדי למנוע בחירה שגויה בהזמנה.",
      "הרשימה מוצגת כברירת מחדל בסדר א׳–ב׳; לחיצה על כותרת עמודת הספק מחליפה בין סדר עולה לסדר יורד.",
    ],
    tips: ["לפני יצירת ספק נוסף, חפש אותו ברשימה כדי לצמצם כפילויות."],
    link: { href: "/dashboard/suppliers", label: "פתיחת מסך ספקים" },
  },
  {
    id: "catalog",
    title: "מוצרים ומחירים",
    icon: Package,
    intro: "הקטלוג מרכז את המוצרים ואת נתוני המחיר המשמשים להשוואה ולרכש.",
    steps: [
      "חפש מוצר קיים לפני הוספת מוצר חדש, ובדוק אם הוא כבר קיים בשם חלופי.",
      "עדכן פרטי מוצר רק לאחר אימות הנתונים.",
      "בדוק הצעות מחיר של ספקים שונים עבור אותו מוצר. מוצר כללי והשם שבו ספק מסוים מציג אותו אינם בהכרח אותו שדה.",
      "כאשר קיימות כמה הצעות או שמות דומים, ודא שהיחידה, הגודל/האריזה והמאפיינים תואמים לפני השוואה.",
      "אל תתייחס למחיר חסר כאילו הוא מחיר אפס; בדוק את מקור המחיר ואת מועד העדכון.",
    ],
    tips: ["איחוד שמות או מיפוי בין מוצר לספק הוא החלטה שמשפיעה על ההשוואות. אשר התאמה רק כשהיא חד-משמעית."],
    link: { href: "/dashboard/catalog", label: "פתיחת מוצרים ומחירים" },
  },
  {
    id: "orders",
    title: "הזמנות רכש",
    icon: ShoppingCart,
    intro: "הזמנה מרכזת את הספק, המוצרים והכמויות שרוצים לרכוש.",
    steps: [
      "פתח את מסך הזמנות הרכש והתחל הזמנה בהתאם לאפשרויות המוצגות.",
      "בחר את הספק הנכון והוסף את הפריטים והכמויות.",
      "בדוק את יחידות המידה, הכמויות והפרטים לפני שמירה או שליחה.",
      "פתח הזמנה קיימת כדי לבדוק את פרטיה ואת מצבה ולעבוד עליה בהתאם להרשאות שלך.",
      "אם יש ספק לגבי מחיר או חלופה, עבור להשוואת מחירים לפני אישור החלטת הרכש.",
    ],
    tips: ["בדוק את ההזמנה לפני שליחתה לספק; אל תניח ששמירה במערכת פירושה שההזמנה כבר נשלחה."],
    link: { href: "/dashboard/orders", label: "פתיחת הזמנות רכש" },
  },
  {
    id: "inventory",
    title: "מלאי וספירות",
    icon: Warehouse,
    intro: "השתמש במסך זה כדי לעיין בנתוני המלאי ובתהליכי הספירה הקיימים במערכת.",
    steps: [
      "פתח את מסך מלאי וספירות ובחר את המוצר או את הספירה הרלוונטיים.",
      "בעת ספירה פיזית, הקפד להזין את הכמות שנבדקה בפועל ולוודא את תאריך הספירה.",
      "בדוק אם קיימות ספירות חוזרות או נתונים חריגים לפני שמסיקים מסקנות על צריכה.",
      "תחזיות צריכה והמלצות להזמנה הן כלי עזר המבוסס על הנתונים הזמינים, ואינן תחליף לבדיקה פיזית ולאישור אנושי.",
    ],
    tips: ["אם נתוני צריכה אינם זמינים, בדוק שהספירות הוזנו כראוי ונסה לרענן את המסך; אל תמציא כמות חסרה."],
    link: { href: "/dashboard/inventory", label: "פתיחת מלאי וספירות" },
  },
  {
    id: "prices",
    title: "השוואת מחירים",
    icon: BarChart3,
    intro: "מסך השוואת המחירים מסייע לבדוק פערים בין הצעות ספקים ולזהות אפשרויות לחיסכון.",
    steps: [
      "בחר מוצר או השתמש באפשרויות הסינון הזמינות כדי למקד את הבדיקה.",
      "השווה את ההצעות הזמינות של הספקים לאותו מוצר, תוך בדיקת יחידות, אריזות ותאריך המחיר.",
      "השתמש במסננים ובאפשרויות ההשוואה הזמינות במסך כדי לנתח לפי מוצר או קבוצת מוצרים/קטגוריה, כאשר הנתונים תומכים בכך.",
      "בדוק פערי מחיר, מגמות או חריגות מול נתוני המקור. הצעה חסרה אינה הוכחה שהספק יקר או זול יותר.",
      "לפני שינוי מחיר או החלטת רכש, ודא שהמוצר וההצעה תואמים ושהנתון מעודכן.",
    ],
    tips: ["השוואה תקינה דורשת מוצרים בני-השוואה ובסיס מחיר אחיד. בדוק מע״מ, יחידת מידה וגודל אריזה כאשר המידע זמין."],
    link: { href: "/dashboard/price-intelligence", label: "פתיחת השוואת מחירים" },
  },
  {
    id: "procurement",
    title: "תמונת מצב רכש ומרכז החלטות",
    icon: BrainCircuit,
    intro: "המסך מרכז תובנות וכלי ניתוח המסייעים להבין את מצב הרכש, לזהות הזדמנויות ולתעדף בדיקות.",
    steps: [
      "עבור על המדדים, השינויים וההזדמנויות המוצגים במסך.",
      "פתח את פרטי ההזדמנות ובדוק על אילו מוצרים, ספקים ומחירים היא מבוססת.",
      "התייחס לתובנות AI כסיוע לניתוח ולא כמקור אמת עצמאי; אמת אותן מול הנתונים במערכת.",
      "בדוק שהחיסכון המשוער מבוסס על הצעות עדכניות ועל כמויות או הנחות רלוונטיות לפני שמציגים אותו כחיסכון בפועל.",
      "החלטה על ספק, שינוי מחיר או הזמנה נשארת באחריות המשתמש ובהתאם להרשאותיו.",
    ],
    tips: ["חיסכון פוטנציאלי אינו חיסכון שמומש. יש להפריד בין הזדמנות מחושבת לבין רכישה שבוצעה בפועל."],
    link: { href: "/dashboard/procurement-intelligence", label: "פתיחת תמונת מצב רכש" },
  },
  {
    id: "documents",
    title: "מסמכים וקליטה",
    icon: FileSearch,
    intro: "המסך מיועד לעבודה עם מסמכי ספק, חילוץ נתונים ובדיקת התאמות לפני קליטתם.",
    steps: [
      "העלה או פתח מסמך דרך תהליך הקליטה הקיים במסך.",
      "בדוק את הספק שזוהה, פרטי המסמך ושורות המוצרים שחולצו.",
      "בדוק התאמות בין שורת מסמך למוצר בקטלוג. אם ההתאמה אינה ודאית, בחן את החלופות במקום לאשר אוטומטית.",
      "בדוק כמות, יחידה, מחיר, תאריך וסכומים מול המסמך המקורי לפני אישור.",
      "בדוק את מצב התהליך ואת ההיסטוריה כדי לוודא אם המסמך כבר נותח או נקלט, וכדי למנוע עבודה כפולה.",
    ],
    tips: ["חילוץ באמצעות AI עלול לטעות. המסמך המקורי הוא המקור לבדיקה, ויש לאשר שורות לא ודאיות באופן ידני."],
    link: { href: "/dashboard/document-intelligence", label: "פתיחת מסמכים וקליטה" },
  },
  {
    id: "calendar",
    title: "יומן ותזכורות",
    icon: CalendarDays,
    intro: "השתמש ביומן כדי לעקוב אחר תזכורות ופעולות מתוכננות הזמינות במערכת.",
    steps: [
      "פתח את היומן ובדוק תזכורות לפי התאריך המוצג.",
      "בעת יצירה או עדכון של תזכורת, ודא שהמועד והפרטים נכונים.",
      "בדוק את היומן באופן שוטף כדי שלא לפספס פעולות המשך מול ספקים או מסמכים.",
    ],
    link: { href: "/dashboard/calendar", label: "פתיחת יומן ותזכורות" },
  },
  {
    id: "audit",
    title: "היסטוריית פעולות",
    icon: History,
    intro: "היסטוריית הפעולות מסייעת לעקוב אחר פעולות שבוצעו במערכת ולבדוק שינויים.",
    steps: [
      "פתח את המסך וחפש את הפעולה או פרק הזמן הרלוונטיים באמצעות אפשרויות הסינון הזמינות.",
      "השתמש ברישום כדי לברר מה השתנה ומתי, ככל שהפרטים מוצגים באירוע.",
      "אם פעולה נראית לא צפויה, בדוק את הפרטים ואת ההרשאות ופנה למנהל המערכת לפי הצורך.",
    ],
    link: { href: "/dashboard/audit", label: "פתיחת היסטוריית פעולות" },
  },
  {
    id: "settings",
    title: "הגדרות והרשאות",
    icon: Settings,
    intro: "מסך ההגדרות מציג אפשרויות תצורה בהתאם לתפקיד ולהרשאות המשתמש.",
    steps: [
      "בדוק את ההגדרות הזמינות בחשבון שלך לפני שינוי התנהגות המערכת.",
      "שנה רק פרטים שאתה מוסמך לנהל, ובדוק את התוצאה לאחר השמירה.",
      "אם אפשרות אינה מופיעה, ייתכן שהיא מוגבלת לתפקיד או להרשאה אחרת.",
    ],
    link: { href: "/dashboard/settings", label: "פתיחת הגדרות" },
  },
  {
    id: "admin",
    title: "ניהול מערכת",
    icon: ShieldCheck,
    intro: "כלי ניהול המערכת זמינים למשתמשים בעלי ההרשאות המתאימות בלבד.",
    steps: [
      "השתמש בניהול מערכת לניהול משתמשים והרשאות, ולפעולות הניהול שמוצגות בחשבון שלך.",
      "לפני השבתה, מחיקה או שינוי רחב, בדוק את הישות ואת ההשפעה של הפעולה.",
      "אל תשתף סיסמאות או פרטי גישה. הענק לכל משתמש רק את ההרשאות הדרושות לתפקידו.",
      "לאחר פעולה משמעותית, בדוק את התוצאה ואת רישום הפעולה כאשר הוא זמין.",
    ],
    tips: ["פעולות מנהל עשויות להשפיע על משתמשים נוספים או על נתוני הרכש. בצע אותן בזהירות."],
    link: { href: "/dashboard/admin", label: "פתיחת ניהול מערכת" },
  },
  {
    id: "troubleshooting",
    title: "פתרון תקלות נפוצות",
    icon: Lightbulb,
    intro: "לפני שמנסים שוב פעולה, כדאי לבדוק האם היא כבר הסתיימה ומהו מקור התקלה.",
    steps: [
      "מסך לא מתעדכן: רענן את המסך פעם אחת ובדוק אם הנתונים נטענו.",
      "מוצר או ספק לא מופיעים: בדוק חיפוש, מסננים, סטטוס פעיל והרשאות.",
      "אין הצעות מחיר להשוואה: בדוק שהמוצר משויך להצעות ספק ושיש להן מחירים מעודכנים.",
      "מסמך נכשל בניתוח או בקליטה: פתח את פרטי התהליך, בדוק את השגיאה ואת המסמך המקורי, ואל תאשר נתונים חלקיים בלי בדיקה.",
      "פעולה נכשלה: בדוק את הודעת השגיאה לפני ניסיון חוזר כדי לצמצם כפילויות.",
      "בעיה נמשכת: רשום את המסך, הפעולה, מועד התקלה והודעת השגיאה ופנה למנהל המערכת.",
    ],
  },
];

const workflow = [
  { label: "ספקים", detail: "בדיקת ספק ופרטי קשר", href: "/dashboard/suppliers" },
  { label: "מוצרים ומחירים", detail: "בדיקת קטלוג והצעות", href: "/dashboard/catalog" },
  { label: "השוואת מחירים", detail: "בחינת חלופות ופערים", href: "/dashboard/price-intelligence" },
  { label: "הזמנות רכש", detail: "הזנה ובדיקת פריטים", href: "/dashboard/orders" },
];

export default function HelpPage() {
  const [open, setOpen] = useState("start");
  return (
    <main dir="rtl" className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="rounded-3xl bg-gradient-to-br from-indigo-700 to-violet-700 p-6 text-white shadow-xl sm:p-8">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/15"><HelpCircle className="h-6 w-6" /></div>
          <div>
            <p className="text-sm font-bold text-indigo-100">ישיבת אוהבי ירושלים - ראשית</p>
            <h1 className="mt-1 text-2xl font-black sm:text-3xl">מרכז העזרה</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">מדריך מעשי לפי המסכים הקיימים במערכת: רכש שוטף, קטלוג ומחירים, מלאי, ניתוח נתונים, מסמכים, מעקב וניהול.</p>
          </div>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-6">
        <div className="mb-4 flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><h2 className="font-black text-slate-900 dark:text-white">מסלול עבודה מומלץ</h2></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {workflow.map((item, i) => (
            <Link key={item.href} href={item.href} className="group rounded-xl border border-slate-200 bg-slate-50 p-4 transition hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/30">
              <div className="flex items-center justify-between gap-2"><span className="text-xs font-black text-indigo-600 dark:text-indigo-300">שלב {i + 1}</span><ArrowLeft className="h-4 w-4 text-slate-400 transition group-hover:-translate-x-1" /></div>
              <div className="mt-2 font-black text-slate-900 dark:text-white">{item.label}</div>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{item.detail}</p>
            </Link>
          ))}
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-500 dark:text-slate-400">המסלול הוא המלצה ולא תהליך אוטומטי: יש לבדוק נתונים ולאשר פעולות לפני ביצוען.</p>
      </section>

      <section className="space-y-2">
        {sections.map(({ id, title, icon: Icon, intro, steps, tips, link }) => {
          const active = open === id;
          return (
            <div key={id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
              <button type="button" onClick={() => setOpen(active ? "" : id)} aria-expanded={active} className="flex w-full items-center gap-3 px-4 py-4 text-right hover:bg-slate-50 dark:hover:bg-slate-900">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"><Icon className="h-4 w-4" /></span>
                <span className="flex-1 font-black text-slate-900 dark:text-white">{title}</span>
                <ChevronDown className={`h-5 w-5 text-slate-400 transition-transform ${active ? "rotate-180" : ""}`} />
              </button>
              {active && (
                <div className="border-t border-slate-100 px-4 pb-5 pt-4 text-sm leading-7 text-slate-600 dark:border-slate-800 dark:text-slate-300 sm:px-6">
                  <p>{intro}</p>
                  <ol className="mt-3 list-decimal space-y-1 pe-5">
                    {steps.map((step) => <li key={step}>{step}</li>)}
                  </ol>
                  {tips?.length ? <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-100"><p className="font-black">חשוב לדעת</p><ul className="mt-1 list-disc space-y-1 pe-5">{tips.map((tip) => <li key={tip}>{tip}</li>)}</ul></div> : null}
                  {link ? <div className="mt-4"><Link href={link.href} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 font-bold text-white transition hover:bg-indigo-700"><span>{link.label}</span><ArrowLeft className="h-4 w-4" /></Link></div> : null}
                </div>
              )}
            </div>
          );
        })}
      </section>
      <footer className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <p className="font-black text-slate-900 dark:text-white">עיקרון מנחה</p>
        <p className="mt-1">המערכת מסייעת לארגן מידע ולקבל החלטות, אך איכות ההשוואה תלויה בנכונות הנתונים. בדוק התאמות, מחירים ותאריכים לפני אישור רכש; תובנות אוטומטיות הן כלי עזר ולא תחליף לבקרה.</p>
      </footer>
    </main>
  );
}
