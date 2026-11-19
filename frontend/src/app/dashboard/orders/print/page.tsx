import { Suspense } from "react";
import OrdersPrintReport from "./orders-print-report";

export default function OrdersPrintPage() {
  return (
    <Suspense fallback={<main className="p-8 text-center text-sm text-slate-500">טוען דוח להדפסה...</main>}>
      <OrdersPrintReport />
    </Suspense>
  );
}
