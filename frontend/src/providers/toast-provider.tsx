"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { AlertCircle, Info, X } from "lucide-react";
import { setToastListener, emitToast, ToastMessage } from "@/lib/toast-bus";
import { cn } from "@/lib/utils";

const ToastContext = createContext<{ showToast: typeof emitToast } | undefined>(undefined);

const AUTO_DISMISS_MS = 5000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    setToastListener((toast) => {
      setToasts((prev) => [...prev, toast]);
      setTimeout(() => dismiss(toast.id), AUTO_DISMISS_MS);
    });
    return () => setToastListener(null);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast: emitToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium shadow-lg",
              t.variant === "error" ? "bg-red-600 text-white" : "bg-slate-900 text-white"
            )}
          >
            {t.variant === "error" ? <AlertCircle size={16} /> : <Info size={16} />}
            <span>{t.message}</span>
            <button onClick={() => dismiss(t.id)} className="ml-2 opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
};
