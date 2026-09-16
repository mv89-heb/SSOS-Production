"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Barcode, RefreshCw } from "lucide-react";
import Link from "next/link";
import InventoryBarcodeManager from "@/components/inventory/inventory-barcode-manager";
import { inventoryService } from "@/services/inventory-service";

export default function InventoryBarcodesPage() {
  const queryClient = useQueryClient();
  const summary = useQuery({ queryKey: ["inventory", "summary"], queryFn: inventoryService.getSummary, staleTime: 20_000 });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["inventory", "summary"] });
  };

  if (summary.isLoading) {
    return <div dir="rtl" className="p-8 text-center text-sm text-slate-500">טוען את קטלוג המלאי…</div>;
  }

  return (
    <div dir="rtl" className="space-y-5 pb-12">
      <header className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Link href="/dashboard/inventory" className="mb-3 inline-flex items-center gap-2 text-xs font-black text-indigo-600"><ArrowRight size={15} /> חזרה למלאי</Link>
            <div className="flex items-center gap-2"><Barcode className="text-indigo-600" size={24} /><h1 className="text-3xl font-black">ברקודים ומדבקות</h1></div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">המערכת מייצרת ברקוד פנימי ייחודי לכל מוצר שחסר לו ברקוד. הברקוד שייך למוצר הארגוני ואינו משתנה כשמחליפים ספק.</p>
          </div>
          <button onClick={refresh} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black dark:border-slate-700"><RefreshCw size={17} /> רענן</button>
        </div>
      </header>

      {summary.error ? <div className="rounded-2xl bg-red-50 p-4 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-300">לא ניתן לטעון את המלאי כרגע.</div> : (
        <InventoryBarcodeManager
          open
          products={summary.data?.products ?? []}
          onClose={() => window.location.href = "/dashboard/inventory"}
          onRefresh={refresh}
        />
      )}
    </div>
  );
}
