"use client";

import {
  Archive, ArrowLeft, BellRing, CalendarDays, CheckCircle2, CircleHelp,
  FileSpreadsheet, FileText, History, KeyRound, LayoutDashboard, Package,
  Settings2, ShieldCheck, ShoppingBag, Users, Warehouse, Building2, UserRound,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import type { UserRole } from "@/types";

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "מנהל מערכת",
  manager: "מנהל",
  employee: "עובד",
};

type SettingsLink = {
  title: string;
  description: string;
  href: string;
  icon: typeof Settings2;
  tag?: string;
};

function SettingsCard({ title, description, href, icon: Icon, tag }: SettingsLink) {
  return (
    <Link
      href={href}
      className="group flex min-w-0 items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-800"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
        <Icon size={21} aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
          {title}
          {tag && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{tag}</span>}
        </span>
        <span className="mt-1 block text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</span>
      </span>
      <ArrowLeft size={17} className="mt-1 shrink-0 text-slate-400 transition group-hover:-translate-x-1 group-hover:text-indigo-600" aria-hidden="true" />
    </Link>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">{title}</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{children}</div>
    </section>
  );
}

export default function SettingsPage() {
  const { user, tenant } = useAuth();
  const canManageImports = permissions.canManageImports(user);
  const canManageUsers = permissions.canManageUsers(user);
  const canViewAudit = permissions.canViewAudit(user);

  return (
    <div dir="rtl" className="space-y-8 pb-10">
      <header className="overflow-hidden rounded-3xl bg-gradient-to-l from-[#071d33] via-[#12375a] to-indigo-800 p-6 text-white shadow-lg sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-indigo-100">
              <Settings2 size={14} /> מרכז הגדרות ותחזוקה
            </div>
            <h1 className="text-2xl font-black sm:text-3xl">הגדרות המערכת</h1>
            <p className="mt-2 text-sm leading-6 text-slate-200 sm:text-base">
              נקודת כניסה אחת לחשבון, לארגון, להרשאות, לחיבורים ולכלי תחזוקת הנתונים.
              פעולות שעדיין אינן נתמכות אינן מוצגות כהגדרות פעילות.
            </p>
          </div>
          <Link href="/dashboard/help" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-white/25 bg-white/10 px-4 py-2.5 text-sm font-bold transition hover:bg-white/20">
            <CircleHelp size={17} /> מרכז העזרה
          </Link>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400"><UserRound size={15} /> החשבון שלך</div>
          <p className="mt-3 break-words text-base font-bold text-slate-900 dark:text-white">{user?.full_name ?? "הפרופיל נטען…"}</p>
          <p className="mt-1 break-words text-sm text-slate-500 dark:text-slate-400">{user?.email ?? "—"}</p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 size={14} /> {user ? ROLE_LABELS[user.role] : "טוען תפקיד"}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400"><Building2 size={15} /> סביבת העבודה</div>
          <p className="mt-3 break-words text-base font-bold text-slate-900 dark:text-white">{tenant?.name ?? "הארגון נטען…"}</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">מזהה ארגון: {tenant?.slug ?? "—"}</p>
          <p className="mt-4 text-xs leading-5 text-slate-500 dark:text-slate-400">הנתונים כאן לקריאה בלבד; שינוי פרטי הארגון אינו זמין כרגע במסך זה.</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400"><ShieldCheck size={15} /> גישה ואבטחה</div>
          <p className="mt-3 text-base font-bold text-slate-900 dark:text-white">{canManageUsers ? "ניהול משתמשים זמין" : "גישה לפי תפקיד"}</p>
          <p className="mt-1 text-sm leading-5 text-slate-500 dark:text-slate-400">{canManageUsers ? "אפשר לנהל משתמשים והרשאות במרכז הניהול." : "האפשרויות המוצגות מותאמות להרשאות החשבון שלך."}</p>
          {canManageUsers && <Link className="mt-3 inline-flex items-center gap-1 text-sm font-bold text-indigo-700 hover:text-indigo-900 dark:text-indigo-300" href="/dashboard/admin">ניהול משתמשים והרשאות <ArrowLeft size={14} /></Link>}
        </div>
      </section>

      <Section title="חיבורים והתראות" description="חיבורי שירותים ותורי מעקב שכבר קיימים במערכת.">
        <SettingsCard title="Google Calendar" description="בדיקת החיבור, בחירת יומן וסנכרון תזכורות." href="/dashboard/settings/google-calendar" icon={CalendarDays} tag="חיבור חיצוני" />
        <SettingsCard title="מרכז תזכורות" description="מעקב אחר הזמנות שדורשות טיפול, דחיית תזכורת וסימון טיפול שהושלם." href="/dashboard/reminders" icon={BellRing} />
        <SettingsCard title="יומן ותכנון" description="צפייה בתאריכים, אירועים ותזכורות הקשורים לפעילות." href="/dashboard/calendar" icon={LayoutDashboard} />
      </Section>

      <Section title="ייבוא ותחזוקת נתונים" description="כלי טעינה ובקרה. יש לבדוק תצוגה מקדימה והתאמות לפני החלת שינויים על נתונים קיימים.">
        {canManageImports && <SettingsCard title="ייבוא מחירוני ספקים" description="אשף העלאה, מיפוי עמודות, בדיקות תקינות ותצוגה מקדימה לפני הייבוא." href="/dashboard/settings/import" icon={FileSpreadsheet} />}
        {canManageImports && <SettingsCard title="ייבוא היסטורי" description="קליטת חשבוניות ותעודות משלוח היסטוריות עם סקירת כפילויות, ללא יצירת תנועות מלאי פעילות." href="/dashboard/settings/historical-import" icon={Archive} tag="כלי ייעודי" />}
        <SettingsCard title="מסמכים וקליטה" description="ניתוח מסמכים, בדיקת חילוץ נתונים והתאמת פריטים וספקים." href="/dashboard/document-intelligence" icon={FileText} />
        <SettingsCard title="מוצרים ומחירים" description="ניהול קטלוג, בדיקת נתוני מוצרים והצעות מחיר של ספקים." href="/dashboard/catalog" icon={Package} />
        {canManageImports && <SettingsCard title="ברקודים ותוויות" description="יצירת ברקוד פנימי ו־QR למוצרים, הצגה והדפסה בלי לשנות ברקודי ספק." href="/dashboard/settings/product-codes" icon={Package} tag="חדש" />
      </Section>

      <Section title="ניהול, בקרה ותיעוד" description="כלים לבדיקת פעולות המערכת, הרשאות ותהליכי עבודה.">
        {canManageUsers && <SettingsCard title="מרכז ניהול מערכת" description="ניהול משתמשים, תפקידים והרשאות וכן צפייה בנתוני ניהול." href="/dashboard/admin" icon={Users} />}
        {canViewAudit && <SettingsCard title="יומן פעולות" description="עיון בפעולות המתועדות במערכת, לפי הרשאות המשתמש." href="/dashboard/audit" icon={History} />}
        {canManageUsers && <SettingsCard title="בדיקת שלמות יומן הביקורת" description="בדיקת תקינות שרשרת הביקורת במרכז ניהול המערכת." href="/dashboard/admin/audit" icon={ShieldCheck} tag="מנהל מערכת" />}
        <SettingsCard title="הזמנות רכש" description="גישה לתהליך ההזמנה, סטטוסים ופרטי ההזמנות." href="/dashboard/orders" icon={ShoppingBag} />
        <SettingsCard title="מלאי וספירות" description="גישה למלאי, לספירות ולכלי תכנון המלאי." href="/dashboard/inventory" icon={Warehouse} />
      </Section>

      <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm dark:border-slate-700 dark:bg-slate-900/50 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <KeyRound className="mt-0.5 shrink-0 text-slate-500" size={19} />
          <div>
            <p className="font-bold text-slate-800 dark:text-slate-200">מה עדיין לא מוגדר כאן?</p>
            <p className="mt-1 leading-6 text-slate-600 dark:text-slate-400">עריכת פרטי ארגון, העדפות התראות אישיות, שפה ואזור זמן, ומדיניות סיסמאות מרוכזת דורשים מסכי הגדרות ייעודיים. לא הוספנו מתגים דמה שאינם שומרים שינוי בפועל.</p>
          </div>
        </div>
        <Link href="/dashboard/help" className="inline-flex shrink-0 items-center gap-2 font-bold text-indigo-700 hover:text-indigo-900 dark:text-indigo-300">הנחיות שימוש <ArrowLeft size={15} /></Link>
      </div>
    </div>
  );
}
