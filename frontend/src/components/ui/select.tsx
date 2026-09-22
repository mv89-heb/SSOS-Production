import { Children, SelectHTMLAttributes, ReactElement, forwardRef, isValidElement } from "react";
import { cn } from "@/lib/utils";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, sortOptions = false, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(
          "block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 transition-all focus:border-primary focus:ring-2 focus:ring-primary/20",
          className
        )}
        {...props}
      >
        {sortOptions
          ? (() => {
              const options = Children.toArray(children);
              const pinned = options.filter((child) => isValidElement(child) && (child.props as { value?: string }).value === "all");
              const rest = options.filter((child) => !isValidElement(child) || (child.props as { value?: string }).value !== "all");
              return [...pinned, ...rest.sort((a, b) => {
                const text = (child: ReactElement) => String(child.props.children ?? "");
                return text(a as ReactElement).localeCompare(text(b as ReactElement), "he", { sensitivity: "base" });
              })];
            })()
          : children}
      </select>
    );
  }
);
Select.displayName = "Select";
