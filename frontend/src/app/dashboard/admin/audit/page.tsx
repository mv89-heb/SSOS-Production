"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import { adminService } from "@/services/admin-service";
import { useAuth } from "@/providers/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";

export default function AdminAuditHealthPage() {
  const { user } = useAuth();
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [brokenLogId, setBrokenLogId] = useState<number | null | undefined>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const result = await adminService.listAudit({ limit: 100, offset: 0 });
      setChainValid(result.audit_chain_valid);
      setBrokenLogId(result.first_broken_log_id);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "admin") void load();
  }, [user?.role, load]);

  if (user && user.role !== "admin") {
    return <ErrorState title="אין הרשאה" description="בדיקת תקינות יומן הביקורת זמינה למנהל מערכת בלבד." />;
  }

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm font-bold text-indigo-600"><ShieldCheck size={17} /> בקרה ואבטחה</div>
          <h1 className="text-2xl font-black text-slate-900">תקינות המערכת ויומן ביקורת</h1>
          <p className="mt-1 text-sm text-slate-500">בדיקת שלמות שרשרת הביקורת ועיון בפעולות האחרונות בארגון.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/admin"><Button variant="outline"><ArrowRight size={16} className="ml-2" /> חזרה לניהול</Button></Link>
          <Button onClick={() => void load()} disabled={loading}><RefreshCw size={16} className={`ml-2 ${loading ? "animate-spin" : ""}`} /> רענון בדיקה</Button>
        </div>
      </div>

      {error ? (
        <ErrorState title="בדיקת הביקורת נכשלה" description="לא ניתן לטעון את יומן הביקורת או לאמת את שלמות השרשרת. אפשר לנסות שוב." onRetry={() => void load()} />
      ) : (
        <Card>
          <CardHeader><CardTitle className="text-base">מצב שלמות יומן הביקורת</CardTitle></CardHeader>
          <CardContent className="pt-0">
            {loading && chainValid === null ? (
              <p className="text-sm text-slate-500">בודק את שרשרת הביקורת...</p>
            ) : chainValid === true ? (
              <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
                <CheckCircle2 className="mt-0.5 shrink-0" size={21} />
                <div><p className="font-bold">הבדיקה עברה</p><p className="mt-1 text-sm">לא זוהתה שבירה בשרשרת הגיבובים של יומן הביקורת בבדיקה האחרונה.</p></div>
              </div>
            ) : chainValid === false ? (
              <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">
                <AlertTriangle className="mt-0.5 shrink-0" size={21} />
                <div><p className="font-bold">נמצאה אי-התאמה בשרשרת הביקורת</p><p className="mt-1 text-sm">מזהה הרשומה הראשונה שנכשלה בבדיקה: {brokenLogId ?? "לא נמסר"}. יש לשמור את המידע ולבדוק את האירועים לפני ביצוע תיקון ידני.</p></div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">סטטוס הבדיקה עדיין לא זמין.</p>
            )}
            <p className="mt-3 text-xs text-slate-500">הבדיקה מתייחסת לשרשרת הביקורת שהשרת אימת בזמן הטעינה, ולא לניטור רציף.</p>
          </CardContent>
        </Card>
      )}

      <section className="rounded-xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
        <h2 className="text-lg font-black text-slate-900 dark:text-slate-100">עיון באירועי ביקורת</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">רשימת הפעולות המלאה מוצגת במסך לוג הביקורת המרכזי, כדי לשמור על מקור אחד לפרטי האירועים ולמנוע הבדלים בין שתי רשימות.</p>
        <Link href="/dashboard/audit" className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-xl border border-indigo-200 px-4 py-2 text-sm font-bold text-indigo-700 hover:bg-indigo-50 dark:border-indigo-900 dark:text-indigo-300 dark:hover:bg-indigo-950/30">
          <ExternalLink size={16} /> מעבר ללוג הביקורת המרכזי
        </Link>
      </section>
    </div>
  );
}
