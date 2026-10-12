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

    let frame = 0;

    // Keep the scroll viewport LTR so scrollLeft has the same, predictable
    // 0..max range in Chromium/Firefox/Safari. The table itself remains RTL.
    const scrollToRightEdge = () => {
      const maxScrollLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
      viewport.scrollLeft = maxScrollLeft;
      pinnedToRightRef.current = true;
    };

    const updatePinnedState = () => {
      const maxScrollLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
      // In this LTR viewport, the RTL table's first columns are visible at max.
      pinnedToRightRef.current = Math.abs(maxScrollLeft - viewport.scrollLeft) <= 2;
    };

    const scheduleInitialRightEdge = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        scrollToRightEdge();
        // A second frame handles late font/layout measurements in the first paint.
        frame = requestAnimationFrame(() => {
          if (pinnedToRightRef.current) scrollToRightEdge();
        });
      });
    };

    viewport.addEventListener("scroll", updatePinnedState, { passive: true });

    const resizeObserver = new ResizeObserver(() => {
      // Preserve the RTL starting edge on resize only while the user is there.
      if (pinnedToRightRef.current) scrollToRightEdge();
    });

    resizeObserver.observe(viewport);
    resizeObserver.observe(table);
    scheduleInitialRightEdge();

    return () => {
      cancelAnimationFrame(frame);
      viewport.removeEventListener("scroll", updatePinnedState);
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <div className="w-full min-w-0">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-indigo-100 bg-indigo-50/70 px-3 py-2 text-xs text-indigo-900 dark:border-indigo-900/50 dark:bg-indigo-950/30 dark:text-indigo-200">
        <span className="font-semibold">הטבלה רחבה — השתמש בכפתורים כדי לראות את כל העמודות</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => viewportRef.current?.scrollBy({ left: -Math.max(240, (viewportRef.current?.clientWidth ?? 0) * 0.75), behavior: "smooth" })}
            className="rounded-lg border border-indigo-200 bg-white px-3 py-2 font-bold hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 dark:border-indigo-800 dark:bg-slate-900 dark:hover:bg-indigo-950"
            aria-label="גלילה שמאלה להצגת עמודות נוספות"
          >
            ← גלילה שמאלה
          </button>
          <button
            type="button"
            onClick={() => viewportRef.current?.scrollBy({ left: Math.max(240, (viewportRef.current?.clientWidth ?? 0) * 0.75), behavior: "smooth" })}
            className="rounded-lg border border-indigo-200 bg-white px-3 py-2 font-bold hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 dark:border-indigo-800 dark:bg-slate-900 dark:hover:bg-indigo-950"
            aria-label="גלילה ימינה להצגת עמודות נוספות"
          >
            גלילה ימינה →
          </button>
        </div>
      </div>
      <div
      ref={viewportRef}
      dir="ltr"
      role="region"
      aria-label="טבלה רחבה — ניתן לגלול אופקית"
      tabIndex={0}
      className="block w-full min-w-0 max-w-full overflow-x-auto overflow-y-hidden overscroll-x-contain rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 dark:border-slate-800 dark:bg-slate-900 dark:shadow-black/10"
      style={{
        direction: "ltr",
        inlineSize: "100%",
        maxInlineSize: "100%",
        minInlineSize: 0,
        boxSizing: "border-box",
        WebkitOverflowScrolling: "touch",
      }}
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
        "whitespace-normal break-words [overflow-wrap:anywhere] px-4 py-3 text-xs font-bold tracking-wide text-slate-500 dark:text-slate-400",
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
        "whitespace-normal break-words [overflow-wrap:anywhere] px-4 py-3.5 align-top text-slate-700 dark:text-slate-200",
        className,
      )}
      {...props}
    />
  );
}
