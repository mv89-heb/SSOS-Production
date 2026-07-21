"use client";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface WizardStepDef {
  key: string;
  label: string;
}

export function WizardStepper({
  steps,
  currentIndex,
}: {
  steps: WizardStepDef[];
  currentIndex: number;
}) {
  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs">
      {steps.map((step, i) => {
        const isDone = i < currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <li key={step.key} className="flex items-center gap-2">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition-colors",
                isCurrent
                  ? "bg-primary text-white"
                  : isDone
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-400"
              )}
            >
              {isDone ? <Check size={12} /> : <span>{i + 1}</span>}
              <span>{step.label}</span>
            </div>
            {i < steps.length - 1 && <div className="h-px w-4 bg-slate-200" />}
          </li>
        );
      })}
    </ol>
  );
}
