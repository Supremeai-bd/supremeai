"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { Brain, GitMerge, LayoutDashboard, Moon, Command as CommandIcon, RadioTower, ScrollText, Settings2, Sun, Bot, UsersRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { DashboardData } from "@/lib/mission-types";
import { StatusDot } from "./widgets";
import { cn } from "@/lib/utils";

export type TabId = "dashboard" | "tower" | "git" | "brain" | "autonomy" | "journal" | "tenancy" | "settings";

export const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "tower", label: "Tower Explorer", icon: <RadioTower className="h-4 w-4" /> },
  { id: "git", label: "Git Sync", icon: <GitMerge className="h-4 w-4" /> },
  { id: "brain", label: "Brain", icon: <Brain className="h-4 w-4" /> },
  { id: "autonomy", label: "Autonomy", icon: <Bot className="h-4 w-4" /> },
  { id: "journal", label: "Journal", icon: <ScrollText className="h-4 w-4" /> },
  { id: "tenancy", label: "Tenancy", icon: <UsersRound className="h-4 w-4" /> },
  { id: "settings", label: "Settings", icon: <Settings2 className="h-4 w-4" /> },
];

export function Header({ active }: { active: TabId }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const { data } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async (): Promise<DashboardData> => {
      const res = await fetch("/api/dashboard", { cache: "no-store" });
      if (!res.ok) throw new Error("dash");
      return res.json();
    },
    refetchInterval: 60_000,
    retry: 1,
  });

  const tower = data?.tower;
  const isLive = tower?.status === "live";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <RadioTower className="h-4.5 w-4.5" />
            <span className="absolute -right-0.5 -top-0.5">
              <StatusDot status={tower?.status ?? "unknown"} className="h-2 w-2 border border-background" />
            </span>
          </div>
          <div className="leading-tight">
            <p className="text-sm font-bold tracking-tight">
              SupremeAI <span className="text-primary">Mission Control</span>
            </p>
            <p className="hidden text-[10px] uppercase tracking-widest text-muted-foreground sm:block">
              governed autonomy · zero cost
            </p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Tower status pill with live shimmer */}
          <Badge
            variant="secondary"
            className="relative hidden gap-1.5 overflow-hidden font-mono text-[11px] sm:inline-flex"
            aria-live="polite"
          >
            <StatusDot status={tower?.status ?? "unknown"} />
            tower:{tower?.status ?? "…"}
            {tower?.latencyMs != null && <span className="text-muted-foreground">· {tower.latencyMs}ms</span>}
            {isLive && <span className="mc-live absolute inset-0" aria-hidden />}
          </Badge>

          {/* Command palette trigger */}
          <Button
            variant="outline"
            size="sm"
            className="hidden h-8 gap-2 pr-1.5 text-xs text-muted-foreground md:inline-flex"
            onClick={() => window.dispatchEvent(new CustomEvent("mc-palette"))}
            aria-label="Open command palette (Cmd+K)"
          >
            <CommandIcon className="h-3.5 w-3.5" />
            <span className="hidden lg:inline">Commands</span>
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">⌘K</kbd>
          </Button>

          {/* Theme toggle */}
          {mounted && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </div>

      {/* Nav tabs */}
      <nav className="mx-auto max-w-7xl px-4" aria-label="Sections">
        <div className="flex gap-1 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => window.dispatchEvent(new CustomEvent("mc-navigate", { detail: t.id }))}
              aria-current={active === t.id ? "page" : undefined}
              className={cn(
                "relative flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                active === t.id ? "text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {t.icon}
              {t.label}
              {active === t.id && (
                <motion.span
                  layoutId="nav-underline"
                  className="absolute inset-x-2 -bottom-2 h-0.5 rounded-full bg-primary"
                  transition={{ type: "spring", bounce: 0.25, duration: 0.45 }}
                />
              )}
            </button>
          ))}
        </div>
      </nav>
    </header>
  );
}

export function Footer() {
  const [utc, setUtc] = React.useState("");
  React.useEffect(() => {
    const tick = () => setUtc(new Date().toISOString().slice(11, 19) + " UTC");
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await fetch("/api/settings", { cache: "no-store" });
      return res.json();
    },
    staleTime: 60_000,
  });

  let towerHost = "";
  try {
    towerHost = settings?.towerUrl ? new URL(settings.towerUrl).host : "not configured";
  } catch {
    towerHost = "invalid url";
  }

  return (
    <footer className="mt-auto border-t bg-background/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-[11px] text-muted-foreground">
        <p>
          <span className="font-semibold text-foreground/70">SupremeAI</span> · Mission Control v1.9 — Zero Cost · Fast · Intelligent · Easy · Secure · Best-in-Class · Dynamic
        </p>
        <p className="flex items-center gap-3 font-mono">
          <a
            href={settings?.towerUrl ? `${settings.towerUrl}/health` : "#"}
            target="_blank"
            rel="noreferrer"
            className="underline-offset-2 hover:text-primary hover:underline"
          >
            tower: {towerHost}
          </a>
          <span className="tabular-nums">{utc}</span>
        </p>
      </div>
    </footer>
  );
}

export function TabShell({ active, children }: { active: TabId; children: React.ReactNode }) {
  return (
    <AnimatePresence mode="wait">
      <motion.main
        key={active}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="mx-auto w-full max-w-7xl flex-1 px-4 py-6"
      >
        {children}
      </motion.main>
    </AnimatePresence>
  );
}
