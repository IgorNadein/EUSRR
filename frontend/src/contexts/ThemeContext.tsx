"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  applyTheme,
  initializeTheme,
  readThemePreference,
  resolveTheme,
  setThemePreference,
  subscribeToThemeChanges,
  type ResolvedTheme,
  type ThemePreference,
} from "@/lib/theme";

type ThemeContextValue = {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>(() => {
    if (typeof window === "undefined") {
      return "auto";
    }

    return initializeTheme().preference;
  });
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => {
    if (typeof window === "undefined") {
      return "light";
    }

    return initializeTheme().resolved;
  });

  useEffect(() => {
    const sync = () => {
      const preference = readThemePreference();
      const resolved = resolveTheme(preference);
      setThemeState(preference);
      setResolvedTheme(resolved);
    };

    initializeTheme();
    return subscribeToThemeChanges(sync);
  }, []);

  const setTheme = useCallback((nextTheme: ThemePreference) => {
    const resolved = setThemePreference(nextTheme);
    setThemeState(nextTheme);
    setResolvedTheme(resolved);
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
    }),
    [resolvedTheme, setTheme, theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
