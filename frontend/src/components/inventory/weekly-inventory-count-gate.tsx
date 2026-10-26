"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, Loader2 } from "lucide-react";
import { apiClient } from "@/services/api-client";

type CountStatus = {
  active_products: number;
  assigned_products: number;
  counted_products_last_7_days: number;
  completion_percent: number;
  completed: boolean;
  due: boolean;
  next_due_date: string;
};

export default function WeeklyInventoryCountGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => (await apiClient.get<{ user: { role: string } }>("/api/auth/me")).data.user,
    retry: false,
    staleTime: 60_000,
  });
  const status = useQuery({
    queryKey: ["inventory", "count-status"],
    queryFn: async () => (await apiClient.get<{ success: boolean } & CountStatus>("/api/inventory/planning/count-status")).data,
    enabled: me.data?.role === "employee",
    refetchInterval: 60_000,
    retry: false,
  });

  const isCountPage = pathname === "/dashboard/inventory/count" || pathname.startsWith("/dashboard/inventory/count/");
  const required = me.data?.role === "employee" && status.data?.due === true;

  useEffect(() => {
    if (required && !isCountPage) router.replace("/dashboard/inventory/count");
  }, [required, isCountPage, router]);

  if (required && !isCountPage) {
    return (
      <section dir="rtl" className="mx-auto max-w-2xl rounded-3xl border border-amber-300 bg-amber-50 p-6 text-slate-900 shadow-sm dark:border-amber-900 dark:bg-amber-950/30 dark:text-slate-100">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-amber-100 p-3 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200"><AlertTriangle size={26} /></div>
          <div>
            <h2 className="text-xl font-black">נדרשת ספירת מלאי שבועית</h2>
            <p className="mt-2 leading-7">מועד הספירה השבועית הגיע. יש להשלים את קבוצת המוצרים שהוקצתה לשבוע הזה לפני שממשיכים בפעולות במערכת.</p>
            <p className="mt-2 text-sm font-bold">הושלמו {status.data?.completion_percent ?? 0}% מתוך {status.data?.assigned_products ?? 0} מוצרים שהוקצו השבוע.</p>
            <Link href="/dashboard/inventory/count" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-black text-white hover:bg-indigo-700">
              <ClipboardCheck size={18} /> להתחלת ספירת מלאי
            </Link>
          </div>
        </div>
      </section>
    );
  }

  if (me.data?.role === "employee" && status.isLoading && !isCountPage) {
    return <div className="flex items-center justify-center gap-2 p-10 text-sm text-slate-500"><Loader2 className="animate-spin" size={18} /> בודק אם הספירה השבועית הושלמה…</div>;
  }

  return <>{children}</>;
}
