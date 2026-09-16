"use client";

import { useRouter } from "next/navigation";
import InventoryScannerModal from "@/components/inventory/inventory-scanner-modal";

export default function InventoryScanPage() {
  const router = useRouter();

  return (
    <div dir="rtl" className="min-h-[70vh]">
      <InventoryScannerModal open onClose={() => router.push("/dashboard/inventory")} />
    </div>
  );
}
