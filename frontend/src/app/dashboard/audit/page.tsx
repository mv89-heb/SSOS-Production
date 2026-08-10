"use client";
import { ShieldCheck, ClipboardList } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useAuditLogs } from "@/hooks/use-audit";
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Badge } from "@/components/ui/badge";

// The action string always encodes its domain as a prefix (order.created,
// catalog.product_created, auth.login, ...) — reuse that instead of adding
// a separate "entity" field that would just duplicate it.
function entityFromAction(action: string) {
  return action.split(".")[0] ?? action;
}

export default function AuditPage() {
  const { user } = useAuth();
  const canView = permissions.canViewAudit(user);

  const { data: logs, isLoading, isError, refetch } = useAuditLogs();

  if (!canView) {
    return (
      <ErrorState
        title="אין הרשאה"
        description="לוג הביקורת נגיש רק למנהלים."
      />
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">לוג ביקורת</h1>

      {isLoading && (
        <div className="rounded-lg border bg-white shadow-sm">
          <TableSkeleton rows={8} cols={5} />
        </div>
      )}

      {isError && <ErrorState description="טעינת לוג הביקורת נכשלה." onRetry={() => refetch()} />}

      {!isLoading && !isError && (!logs || logs.length === 0) && (
        <EmptyState icon={ClipboardList} title="אין אירועי ביקורת עדיין" description="פעולות שיבוצעו במערכת יופיעו כאן." />
      )}

      {!isLoading && !isError && logs && logs.length > 0 && (
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell>משתמש</TableHeaderCell>
              <TableHeaderCell>פעולה</TableHeaderCell>
              <TableHeaderCell>ישות</TableHeaderCell>
              <TableHeaderCell>תאריך ושעה</TableHeaderCell>
              <TableHeaderCell>גיבוב (Hash)</TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody>
            {logs.map((log) => (
              <TableRow key={log.id}>
                <TableCell className="text-slate-900">{log.user_full_name || log.user_email || "מערכת"}</TableCell>
                <TableCell>
                  <span className="font-mono text-xs text-slate-600">{log.action}</span>
                  {log.title && <div className="text-xs text-slate-400">{log.title}</div>}
                </TableCell>
                <TableCell className="capitalize text-slate-500">{entityFromAction(log.action)}</TableCell>
                <TableCell className="text-slate-500">{new Date(log.created_at).toLocaleString()}</TableCell>
                <TableCell>
                  <Badge variant="success" className="inline-flex items-center gap-1 font-mono">
                    <ShieldCheck size={12} />
                    {log.hash_chain.slice(0, 10)}…
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
