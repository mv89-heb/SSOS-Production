"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/providers/auth-provider";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeContextValue {
  mode: ThemeMode;
  resolvedTheme: "light" | "dark";
  setMode: (mode: ThemeMode) => void;
}

const GUEST_STORAGE_KEY = "ssos-theme:guest";
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getSystemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const storageKey = user?.id ? `ssos-theme:user:${user.id}` : GUEST_STORAGE_KEY;
  const [mode, setModeState] = useState<ThemeMode>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");
  const [loadedKey, setLoadedKey] = useState<string | null>(null);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(storageKey)
        ?? (storageKey === GUEST_STORAGE_KEY ? null : window.localStorage.getItem(GUEST_STORAGE_KEY));
      if (stored === "light" || stored === "dark" || stored === "system") {
        setModeState(stored);
      } else {
        setModeState("system");
      }
    } catch {
      setModeState("system");
    }
    setLoadedKey(storageKey);
  }, [storageKey]);

  useEffect(() => {
    if (loadedKey !== storageKey) return;

    const applyTheme = () => {
      const nextTheme = mode === "system" ? getSystemTheme() : mode;
      setResolvedTheme(nextTheme);
      document.documentElement.classList.toggle("dark", nextTheme === "dark");
      document.documentElement.dataset.theme = nextTheme;
    };

    applyTheme();

    try {
      window.localStorage.setItem(storageKey, mode);
    } catch {
      // Keep the current in-memory choice when storage is unavailable.
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    if (mode !== "system") return;
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [mode, loadedKey, storageKey]);

  const setMode = useCallback((nextMode: ThemeMode) => setModeState(nextMode), []);
  const value = useMemo(() => ({ mode, resolvedTheme, setMode }), [mode, resolvedTheme, setMode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
