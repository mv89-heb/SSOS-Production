import { AlertTriangle } from "lucide-react";
import { Button } from "./button";

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "משהו השתבש",
  description = "נסה שוב.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-red-100 bg-red-50 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-500">
        <AlertTriangle size={22} />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-900">{title}</p>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry} className="mt-2">
          נסה שוב
        </Button>
      )}
    </div>
  );
}
