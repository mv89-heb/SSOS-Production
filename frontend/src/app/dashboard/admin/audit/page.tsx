"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw, ShieldCheck } from "lucide-react";
import { adminService, type AdminAuditLog } from "@/services/admin-service";
import { useAuth } from "@/providers/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/table";

export default function AdminAuditHealthPage() {
  const { user } = useAuth();
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [brokenLogId, setBrokenLogId] = useState<number | null | undefined>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const result = await adminService.listAudit({ limit: 100, offset: 0 });
      setLogs(result.logs);
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

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-black text-slate-900">אירועים אחרונים</h2><span className="text-xs text-slate-500">{logs.length} אירועים מוצגים · עד 100 אחרונים</span></div>
        {error ? null : loading && logs.length === 0 ? (
          <div className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">טוען אירועים...</div>
        ) : logs.length === 0 ? (
          <EmptyState title="אין אירועי ביקורת להצגה" description="אירועים מתועדים יופיעו כאן לאחר ביצוע פעולות במערכת." />
        ) : (
          <div className="overflow-hidden rounded-xl border bg-white">
            <Table>
              <TableHead><tr><TableHeaderCell>תאריך ושעה</TableHeaderCell><TableHeaderCell>פעולה</TableHeaderCell><TableHeaderCell>פרטים</TableHeaderCell><TableHeaderCell>מזהה משתמש</TableHeader></tr></TableHead>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="whitespace-nowrap text-slate-600">{new Date(log.created_at).toLocaleString("he-IL")}</TableCell>
                    <TableCell><span className="font-mono text-xs text-slate-700">{log.action}</span></TableCell>
                    <TableCell className="max-w-md text-slate-600">{log.title || "—"}</TableCell>
                    <TableCell className="text-slate-500">{log.user_id ?? "מערכת"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}
