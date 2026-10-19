"use client";

import { ThemeProvider as NextThemeProvider, useTheme } from "next-themes";
import { useEffect, useState, type ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return <NextThemeProvider attribute="class" defaultTheme="system" enableSystem storageKey="vision-theme">{children}</NextThemeProvider>;
}

export function ThemeControl() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <label className="theme-control">
      <span>Appearance</span>
      <select aria-label="Color theme" disabled={!mounted} value={mounted ? theme : "system"} onChange={(event) => setTheme(event.target.value)}>
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
