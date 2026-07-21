import { OrderStatus } from "@/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<OrderStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  submitted: "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700",
  sent: "bg-indigo-100 text-indigo-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<OrderStatus, string> = {
  draft: "טיוטה",
  submitted: "ממתין לאישור",
  approved: "אושר",
  sent: "נשלח לספק",
  completed: "הושלם",
  cancelled: "בוטל",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2.5 py-1 text-xs font-medium",
        STATUS_STYLES[status]
      )}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

type BadgeVariant = "default" | "success" | "warning" | "danger";

const BADGE_VARIANT_STYLES: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-600",
  success: "bg-green-100 text-green-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
};

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2.5 py-1 text-xs font-medium",
        BADGE_VARIANT_STYLES[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function ActiveBadge({ active }: { active: boolean }) {
  return <Badge variant={active ? "success" : "default"}>{active ? "פעיל" : "לא פעיל"}</Badge>;
}
