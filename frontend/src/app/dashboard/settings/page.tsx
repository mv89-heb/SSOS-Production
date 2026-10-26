"use client";

import { Bell, FileSpreadsheet, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import type { UserRole } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const ROLE_LABELS: Record<UserRole, string> = { admin: "מנהל מערכת", manager: "מנהל רכש", employee: "עובד רכש" };

export default function SettingsPage() {
  const { user, tenant } = useAuth();
  const canManageImports = permissions.canManageImports(user);

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold text-slate-900">הגדרות</h1><p className="mt-1 text-sm text-slate-500">פרופיל, פרטי הארגון והגדרות כלליות.</p></div>
      <Card><CardHeader><CardTitle className="text-base text-slate-900">פרופיל משתמש</CardTitle></CardHeader><CardContent className="pt-0"><dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3"><div><dt className="text-slate-500">שם</dt><dd className="font-medium text-slate-900">{user?.full_name ?? "—"}</dd></div><div><dt className="text-slate-500">אימייל / שם משתמש</dt><dd className="font-medium text-slate-900">{user?.email ?? "—"}</dd></div><div><dt className="text-slate-500">תפקיד</dt><dd>{user ? <Badge variant="default">{ROLE_LABELS[user.role]}</Badge> : "—"}</dd></div></dl></CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base text-slate-900">ארגון</CardTitle></CardHeader><CardContent className="pt-0"><dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2"><div><dt className="text-slate-500">שם הארגון</dt><dd className="text-slate-900">{tenant?.name ?? "—"}</dd></div><div><dt className="text-slate-500">מזהה הארגון</dt><dd className="text-slate-900">{tenant?.slug ?? "—"}</dd></div></dl></CardContent></Card>
      {permissions.canManageUsers(user) && <Card><CardHeader><CardTitle className="text-base text-slate-900">משתמשים והרשאות</CardTitle></CardHeader><CardContent className="pt-0"><div className="flex flex-col gap-3 rounded-lg border border-slate-100 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-medium text-slate-900">ניהול משתמשים במקום מרכזי אחד</p><p className="text-xs text-slate-500">יצירה, שינוי תפקידים והפעלה או השבתה של חשבונות מתבצעים במרכז ניהול המערכת.</p></div><Link href="/dashboard/admin"><Button>פתח ניהול מערכת</Button></Link></div></CardContent></Card>}
      {user?.role === "admin" && <Card><CardHeader><CardTitle className="text-base text-slate-900">תקינות ואבטחת המערכת</CardTitle></CardHeader><CardContent className="pt-0"><div className="flex flex-col gap-3 rounded-lg border border-indigo-100 bg-indigo-50/60 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><ShieldCheck className="mt-0.5 text-indigo-600" size={22} /><div><p className="text-sm font-medium text-slate-900">יומן ביקורת ובדיקת שלמות</p><p className="text-xs leading-5 text-slate-600">בדיקת שרשרת הגיבובים, איתור אי-התאמות ועיון בפעולות האחרונות המתועדות בארגון.</p></div></div><Link href="/dashboard/admin/audit"><Button>פתח מרכז בקרה</Button></Link></div></CardContent></Card>}
      {canManageImports && <Card><CardHeader><CardTitle className="text-base text-slate-900">ייבוא מחירוני ספקים</CardTitle></CardHeader><CardContent className="pt-0"><div className="flex items-center justify-between gap-4 rounded-lg border border-slate-100 bg-slate-50 p-4"><div className="flex items-center gap-3"><FileSpreadsheet className="text-primary" size={22} /><div><p className="text-sm font-medium text-slate-900">טעינת מחירון חדש מקובץ Excel</p><p className="text-xs text-slate-500">סריקה, מיפוי עמודות, בדיקת תקינות ותצוגה מקדימה — לפני שכל נתון נכנס למערכת.</p></div></div><Link href="/dashboard/settings/import"><Button>פתח אשף ייבוא</Button></Link></div></CardContent></Card>}
      <Card><CardHeader><CardTitle className="text-base text-slate-900">העדפות</CardTitle></CardHeader><CardContent className="pt-0"><div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-400"><Bell size={18} /> הגדרות התראות יגיעו בקרוב.</div></CardContent></Card>
    </div>
  );
}
