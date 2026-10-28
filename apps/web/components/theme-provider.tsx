"use client";

import { Moon, Sun } from "lucide-react";
import { ThemeProvider as NextThemeProvider, useTheme } from "next-themes";
import { useEffect, useState, type ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return <NextThemeProvider attribute="class" defaultTheme="dark" enableSystem storageKey="vision-theme">{children}</NextThemeProvider>;
}

export function ThemeControl() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const next = mounted && resolvedTheme === "light" ? "dark" : "light";
  const label = `Switch to ${next} mode`;
  return <button type="button" className="theme-control" disabled={!mounted}
    aria-label={label} title={label} onClick={() => setTheme(next)}>
    <Sun className="theme-sun" size={20} strokeWidth={1.75} aria-hidden="true" />
    <Moon className="theme-moon" size={20} strokeWidth={1.75} aria-hidden="true" />
  </button>;
}
