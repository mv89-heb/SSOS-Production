"use client";

import { cn } from "@/lib/utils";

type SsosLogoProps = {
  size?: "sm" | "md" | "lg";
  light?: boolean;
  wordmark?: boolean;
  className?: string;
};

const sizes = {
  sm: { shell: "h-9 w-9 rounded-xl", mark: "h-6 w-6", text: "text-base" },
  md: { shell: "h-12 w-12 rounded-2xl", mark: "h-8 w-8", text: "text-xl" },
  lg: { shell: "h-20 w-20 rounded-[1.65rem]", mark: "h-14 w-14", text: "text-3xl" },
};

export default function SsosLogo({ size = "md", light = false, wordmark = true, className }: SsosLogoProps) {
  const s = sizes[size];
  return (
    <span className={cn("inline-flex items-center gap-3", className)} dir="ltr" aria-label="SSOS — Smart Supplier Order System">
      <span className={cn("relative inline-flex shrink-0 items-center justify-center overflow-hidden border border-white/15 bg-gradient-to-br from-[#1c8c91] via-[#176b82] to-[#102f50] shadow-lg shadow-[#0c4357]/25", s.shell)}>
        <span className="absolute -right-3 -top-4 h-9 w-9 rounded-full bg-white/20 blur-xl" />
        <svg viewBox="0 0 48 48" className={cn("relative", s.mark)} fill="none" aria-hidden="true">
          <path d="M8 15.5 24 7l16 8.5v17L24 41 8 32.5v-17Z" stroke="white" strokeWidth="2.2" strokeLinejoin="round" />
          <path d="M8.5 16 24 24.5 39.5 16M24 24.5V40" stroke="white" strokeWidth="2" strokeLinejoin="round" />
          <path d="m16 20.2 8-4.5 8 4.5-8 4.5-8-4.5Z" fill="#9FE7D9" />
          <path d="m18 29 6 3.2 6-3.2" stroke="#9FE7D9" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </span>
      {wordmark && (
        <span className="flex min-w-0 flex-col leading-none">
          <span className={cn("font-black tracking-[0.12em]", s.text, light ? "text-white" : "text-slate-950 dark:text-white")}>SSOS</span>
          <span className={cn("mt-1 text-[9px] font-bold tracking-[0.16em]", light ? "text-teal-100/75" : "text-slate-500 dark:text-slate-400")}>SMART PROCUREMENT</span>
        </span>
      )}
    </span>
  );
}
