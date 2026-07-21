"use client";
import { useAuth } from "@/providers/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { permissions } from "@/lib/permissions";
import { Bell, FileSpreadsheet } from "lucide-react";
import Link from "next/link";

const ROLE_LABELS: Record<string, string> = {
  admin: "מנהל מערכת",
  manager: "מנהל",
  employee: "עובד",
};

export default function SettingsPage() {
  const { user, tenant } = useAuth();
  const canManageImports = permissions.canManageImports(user);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">הגדרות</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">פרופיל משתמש</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">שם</dt>
              <dd className="text-slate-900">{user?.full_name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">אימייל</dt>
              <dd className="text-slate-900">{user?.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">תפקיד</dt>
              <dd>
                <Badge variant="default">{user ? ROLE_LABELS[user.role] ?? user.role : "—"}</Badge>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">ארגון</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">שם הארגון</dt>
              <dd className="text-slate-900">{tenant?.name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">מזהה הארגון</dt>
              <dd className="text-slate-900">{tenant?.slug ?? "—"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {canManageImports && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-slate-900">ייבוא מחירוני ספקים</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex items-center justify-between gap-4 rounded-lg border border-slate-100 bg-slate-50 p-4">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="text-primary" size={22} />
                <div>
                  <p className="text-sm font-medium text-slate-900">טעינת מחירון חדש מקובץ Excel</p>
                  <p className="text-xs text-slate-500">סריקה, מיפוי עמודות, בדיקת תקינות ותצוגה מקדימה — לפני שכל נתון נכנס למערכת.</p>
                </div>
              </div>
              <Link href="/dashboard/settings/import">
                <Button>פתח אשף ייבוא</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">העדפות</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-400">
            <Bell size={18} />
            הגדרות התראות יגיעו בקרוב.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
