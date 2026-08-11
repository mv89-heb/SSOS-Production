"use client";

import { Info } from "lucide-react";
import type { ReactNode } from "react";

type HelpTooltipProps = {
  text: string;
  children?: ReactNode;
  className?: string;
};

export function HelpTooltip({ text, children, className = "" }: HelpTooltipProps) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children ?? (
        <button type="button" className="inline-flex h-5 w-5 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:hover:bg-slate-800 dark:hover:text-indigo-300" aria-label={text}>
          <Info className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
      <span role="tooltip" className="pointer-events-none absolute bottom-full right-0 z-[100] mb-2 hidden w-max max-w-xs rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium leading-5 text-white shadow-xl group-hover:block group-focus-within:block dark:bg-white dark:text-slate-900">
        {text}
      </span>
    </span>
  );
}
