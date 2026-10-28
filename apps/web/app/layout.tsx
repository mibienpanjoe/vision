import { SessionProvider } from "@/components/session-provider";
import type { Metadata } from "next";
import { ThemeProvider } from "@/components/theme-provider";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/source-serif-4/latin-400.css";
import "@fontsource/source-serif-4/latin-600.css";
import "@fontsource/source-serif-4/latin-400-italic.css";
import "@fontsource/geist-mono/latin-400.css";
import "@fontsource/geist-mono/latin-500.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vision — Your library",
  manifest: "/manifest.webmanifest",
  description: "A private reading workspace for exploring the worlds within your books.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body><ThemeProvider><SessionProvider>{children}</SessionProvider></ThemeProvider></body>
    </html>
  );
}
