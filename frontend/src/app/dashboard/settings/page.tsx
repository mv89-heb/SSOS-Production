"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, FileSpreadsheet, KeyRound, Plus, ShieldCheck, UserCheck, UserX } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { userService, CreateUserInput, UpdateUserInput } from "@/services/user-service";
import { permissions } from "@/lib/permissions";
import type { UserRole } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "מנהל מערכת",
  manager: "מנהל רכש",
  employee: "עובד רכש",
};

function errorMessage(error: unknown): string {
  const response = (error as { response?: { data?: { message?: string; error?: string } } })?.response?.data;
  return response?.message || response?.error || "הפעולה נכשלה. נסה שוב.";
}

export default function SettingsPage() {
  const { user, tenant } = useAuth();
  const queryClient = useQueryClient();
  const canManageImports = permissions.canManageImports(user);
  const canManageUsers = permissions.canManageUsers(user);

  const [form, setForm] = useState<CreateUserInput>({
    email: "",
    full_name: "",
    password: "",
    role: "manager",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const usersQuery = useQuery({
    queryKey: ["tenant-users"],
    queryFn: userService.list,
    enabled: canManageUsers,
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: userService.create,
    onSuccess: () => {
      setForm({ email: "", full_name: "", password: "", role: "manager" });
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["tenant-users"] });
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: UpdateUserInput }) => userService.update(id, input),
    onSuccess: () => {
      setSelectedUser(null);
      setNewPassword("");
      queryClient.invalidateQueries({ queryKey: ["tenant-users"] });
    },
    onError: (error) => setFormError(errorMessage(error)),
  });

  const activeAdmins = useMemo(
    () => usersQuery.data?.filter((item) => item.active && item.role === "admin").length ?? 0,
    [usersQuery.data],
  );

  const createUser = () => {
    setFormError(null);
    if (!form.email.trim() || !form.full_name.trim() || !form.password) {
      setFormError("יש למלא אימייל, שם מלא וסיסמה.");
      return;
    }
    createMutation.mutate({ ...form, email: form.email.trim().toLowerCase(), full_name: form.full_name.trim() });
  };

  const savePassword = (id: number) => {
    if (!newPassword) return;
    setFormError(null);
    updateMutation.mutate({ id, input: { password: newPassword } });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">הגדרות</h1>
        <p className="mt-1 text-sm text-slate-500">ניהול הארגון, המשתמשים והעדפות המערכת.</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base text-slate-900">פרופיל משתמש</CardTitle></CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <div><dt className="text-slate-500">שם</dt><dd className="font-medium text-slate-900">{user?.full_name ?? "—"}</dd></div>
            <div><dt className="text-slate-500">אימייל / שם משתמש</dt><dd className="font-medium text-slate-900">{user?.email ?? "—"}</dd></div>
            <div><dt className="text-slate-500">תפקיד</dt><dd>{user ? <Badge variant="default">{ROLE_LABELS[user.role]}</Badge> : "—"}</dd></div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base text-slate-900">ארגון</CardTitle></CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div><dt className="text-slate-500">שם הארגון</dt><dd className="text-slate-900">{tenant?.name ?? "—"}</dd></div>
            <div><dt className="text-slate-500">מזהה הארגון</dt><dd className="text-slate-900">{tenant?.slug ?? "—"}</dd></div>
          </dl>
        </CardContent>
      </Card>

      {canManageUsers && (
        <Card className="border-indigo-100 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2 text-base text-slate-900"><ShieldCheck size={19} className="text-indigo-600" /> משתמשים והרשאות</CardTitle>
                <p className="mt-1 text-xs text-slate-500">רק מנהל מערכת יכול ליצור משתמשים, לשנות תפקידים או להשבית חשבונות.</p>
              </div>
              <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">{activeAdmins} מנהלי מערכת פעילים</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-6 pt-0">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-800"><Plus size={17} /> הוספת משתמש</h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <Input placeholder="אימייל / שם משתמש" value={form.email} onChange={(e) => setForm((v) => ({ ...v, email: e.target.value }))} />
                <Input placeholder="שם מלא" value={form.full_name} onChange={(e) => setForm((v) => ({ ...v, full_name: e.target.value }))} />
                <Input type="password" placeholder="סיסמה זמנית" value={form.password} onChange={(e) => setForm((v) => ({ ...v, password: e.target.value }))} />
                <div className="flex gap-2"><Select value={form.role} onChange={(e) => setForm((v) => ({ ...v, role: e.target.value as UserRole }))} className="min-w-0 flex-1"><option value="manager">מנהל רכש</option><option value="employee">עובד רכש</option><option value="admin">מנהל מערכת</option></Select><Button onClick={createUser} disabled={createMutation.isPending}>{createMutation.isPending ? "יוצר..." : "הוסף"}</Button></div>
              </div>
              {formError && <p className="mt-3 text-sm font-medium text-red-600">{formError}</p>}
              <p className="mt-2 text-xs text-slate-400">הסיסמה נשמרת בשרת כ-hash בלבד. מומלץ לתת למשתמש סיסמה זמנית ולשנותה לאחר הכניסה.</p>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[760px] text-sm">
                <thead className="bg-slate-50 text-right text-xs font-bold text-slate-500"><tr><th className="px-4 py-3">משתמש</th><th className="px-4 py-3">תפקיד</th><th className="px-4 py-3">סטטוס</th><th className="px-4 py-3">פעולות</th></tr></thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {usersQuery.isLoading && <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">טוען משתמשים...</td></tr>}
                  {usersQuery.isError && <tr><td colSpan={4} className="px-4 py-8 text-center text-red-500">{errorMessage(usersQuery.error)}</td></tr>}
                  {usersQuery.data?.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3"><div className="font-bold text-slate-900">{item.full_name}</div><div className="text-xs text-slate-400">{item.email}</div></td>
                      <td className="px-4 py-3"><Select value={item.role} disabled={item.id === user?.id} onChange={(e) => updateMutation.mutate({ id: item.id, input: { role: e.target.value as UserRole } })} className="h-9 w-36"><option value="employee">עובד רכש</option><option value="manager">מנהל רכש</option><option value="admin">מנהל מערכת</option></Select></td>
                      <td className="px-4 py-3">{item.active ? <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700"><UserCheck size={13}/> פעיל</span> : <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-500"><UserX size={13}/> מושבת</span>}</td>
                      <td className="px-4 py-3"><div className="flex flex-wrap items-center gap-2">
                        <Button variant="ghost" size="sm" disabled={item.id === user?.id || updateMutation.isPending} onClick={() => updateMutation.mutate({ id: item.id, input: { active: !item.active } })}>{item.active ? "השבת" : "הפעל"}</Button>
                        {item.id !== user?.id && <Button variant="ghost" size="sm" onClick={() => { setSelectedUser(selectedUser === item.id ? null : item.id); setNewPassword(""); }}><KeyRound size={14} /> סיסמה</Button>}
                      </div>{selectedUser === item.id && <div className="mt-2 flex max-w-sm gap-2"><Input type="password" placeholder="סיסמה חדשה" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /><Button size="sm" onClick={() => savePassword(item.id)} disabled={!newPassword || updateMutation.isPending}>שמור</Button></div>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {canManageImports && (
        <Card>
          <CardHeader><CardTitle className="text-base text-slate-900">ייבוא מחירוני ספקים</CardTitle></CardHeader>
          <CardContent className="pt-0"><div className="flex items-center justify-between gap-4 rounded-lg border border-slate-100 bg-slate-50 p-4"><div className="flex items-center gap-3"><FileSpreadsheet className="text-primary" size={22} /><div><p className="text-sm font-medium text-slate-900">טעינת מחירון חדש מקובץ Excel</p><p className="text-xs text-slate-500">סריקה, מיפוי עמודות, בדיקת תקינות ותצוגה מקדימה — לפני שכל נתון נכנס למערכת.</p></div></div><Link href="/dashboard/settings/import"><Button>פתח אשף ייבוא</Button></Link></div></CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base text-slate-900">העדפות</CardTitle></CardHeader>
        <CardContent className="pt-0"><div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-400"><Bell size={18} /> הגדרות התראות יגיעו בקרוב.</div></CardContent>
      </Card>
    </div>
  );
}
