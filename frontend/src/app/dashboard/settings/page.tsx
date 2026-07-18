"use client";
import { useAuth } from "@/providers/auth-provider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bell } from "lucide-react";

export default function SettingsPage() {
  const { user, tenant } = useAuth();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">User Profile</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">Name</dt>
              <dd className="text-slate-900">{user?.full_name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Email</dt>
              <dd className="text-slate-900">{user?.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Role</dt>
              <dd>
                <Badge variant="default" className="capitalize">{user?.role ?? "—"}</Badge>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">Organization</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">Tenant name</dt>
              <dd className="text-slate-900">{tenant?.name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Tenant slug</dt>
              <dd className="text-slate-900">{tenant?.slug ?? "—"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">Preferences</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center gap-3 rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-400">
            <Bell size={18} />
            Notification preferences are coming soon.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
