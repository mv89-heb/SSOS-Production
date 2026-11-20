"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";

interface ThemeContextValue {
  mode: ThemeMode;
  resolvedTheme: "light" | "dark";
  setMode: (mode: ThemeMode) => void;
}

const STORAGE_KEY = "ssos-theme";
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getSystemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "light" || stored === "dark" || stored === "system") {
        setModeState(stored);
      }
    } catch {
      // Storage may be unavailable; the system preference remains usable.
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;

    const applyTheme = () => {
      const nextTheme = mode === "system" ? getSystemTheme() : mode;
      setResolvedTheme(nextTheme);
      document.documentElement.classList.toggle("dark", nextTheme === "dark");
      document.documentElement.dataset.theme = nextTheme;
    };

    applyTheme();

    try {
      window.localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // Keep the current in-memory choice when storage is unavailable.
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    if (mode !== "system") return;
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [mode, ready]);

  const setMode = useCallback((nextMode: ThemeMode) => setModeState(nextMode), []);
  const value = useMemo(() => ({ mode, resolvedTheme, setMode }), [mode, resolvedTheme, setMode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
