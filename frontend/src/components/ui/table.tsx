import { useEffect, useRef, type HTMLAttributes, type TdHTMLAttributes, type ThHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Table({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableElement>) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const tableRef = useRef<HTMLTableElement>(null);
  const pinnedToRightRef = useRef(true);

  useEffect(() => {
    const viewport = viewportRef.current;
    const table = tableRef.current;
    if (!viewport || !table) return;

    // The scroll viewport is LTR, so its maximum scrollLeft exposes
    // the physical right edge of the RTL table (SKU/name columns).
    const scrollToRightEdge = () => {
      viewport.scrollLeft = viewport.scrollWidth;
      pinnedToRightRef.current = true;
    };

    const updatePinnedState = () => {
      const maxScrollLeft = viewport.scrollWidth - viewport.clientWidth;
      pinnedToRightRef.current =
        Math.abs(maxScrollLeft - viewport.scrollLeft) <= 2;
    };

    scrollToRightEdge();
    viewport.addEventListener("scroll", updatePinnedState, { passive: true });

    // Keep the initial RTL edge visible when fonts, rows, or responsive
    // widths change, but do not override a user's deliberate scroll position.
    const resizeObserver = new ResizeObserver(() => {
      if (pinnedToRightRef.current) {
        scrollToRightEdge();
      }
    });

    resizeObserver.observe(viewport);
    resizeObserver.observe(table);

    return () => {
      viewport.removeEventListener("scroll", updatePinnedState);
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <div
      ref={viewportRef}
      dir="ltr"
      className="block w-full min-w-0 max-w-full overflow-x-auto overflow-y-hidden overscroll-x-contain rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/10"
      style={{ direction: "ltr", WebkitOverflowScrolling: "touch" }}
    >
      <table
        ref={tableRef}
        dir="rtl"
        className={cn("w-max min-w-[950px] text-right text-sm", className)}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn(
        "border-b border-slate-200/80 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-950/60",
        className,
      )}
      {...props}
    />
  );
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-slate-100 dark:divide-slate-800", className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "group transition-colors duration-150 hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20",
        className,
      )}
      {...props}
    />
  );
}

export function TableHeaderCell({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "whitespace-nowrap px-4 py-3 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400",
        className,
      )}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn(
        "px-4 py-3.5 text-slate-700 dark:text-slate-200",
        className,
      )}
      {...props}
    />
  );
}
