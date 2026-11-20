import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "outline";
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: ButtonVariant; }

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-primary text-white hover:bg-primary/90 shadow-sm shadow-primary/25",
  secondary: "bg-white text-slate-700 border border-slate-200 hover:border-teal-200 hover:bg-teal-50/60 dark:bg-slate-900 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-sm shadow-red-900/10",
  ghost: "bg-transparent text-slate-600 hover:bg-teal-50 hover:text-teal-800 dark:text-slate-300 dark:hover:bg-slate-800",
  outline: "bg-transparent text-slate-700 border border-slate-200 hover:border-teal-300 hover:bg-teal-50/60 dark:text-slate-100 dark:border-slate-700 dark:hover:bg-slate-800",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", disabled, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} disabled={disabled} aria-disabled={disabled || undefined}
      className={cn("inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-bold tracking-[.005em] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 active:scale-[.985] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60", variantClasses[variant], className)}
      {...props}
    />
  )
);
Button.displayName = "Button";
