"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bot,
  Brain,
  ClipboardCopy,
  Download,
  ExternalLink,
  GitMerge,
  LayoutDashboard,
  Moon,
  RadioTower,
  RefreshCw,
  ScrollText,
  Settings2,
  ShieldAlert,
  Sun,
  UsersRound,
  Zap,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useTheme } from "next-themes";
import { TABS, type TabId } from "./shell";

const TAB_ICONS: Record<TabId, React.ReactNode> = {
  dashboard: <LayoutDashboard className="h-4 w-4" />,
  tower: <RadioTower className="h-4 w-4" />,
  git: <GitMerge className="h-4 w-4" />,
  brain: <Brain className="h-4 w-4" />,
  autonomy: <Bot className="h-4 w-4" />,
  journal: <ScrollText className="h-4 w-4" />,
  tenancy: <UsersRound className="h-4 w-4" />,
  settings: <Settings2 className="h-4 w-4" />,
};

export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const qc = useQueryClient();
  const { theme, setTheme } = useTheme();
  const [pending, setPending] = React.useState<string | null>(null);

  const navigate = React.useCallback((tab: TabId) => {
    setOpen(false);
    window.dispatchEvent(new CustomEvent("mc-navigate", { detail: tab }));
  }, [setOpen]);

  const runAction = React.useCallback(
    async (id: string, label: string, fn: () => Promise<unknown>) => {
      setOpen(false);
      setPending(id);
      toast.promise(fn(), {
        loading: `${label}…`,
        success: (r) => {
          qc.invalidateQueries({ queryKey: ["dashboard"] });
          qc.invalidateQueries({ queryKey: ["git-status"] });
          qc.invalidateQueries({ queryKey: ["git-log"] });
          return `${label} ✓`;
        },
        error: (e) => `${label} failed: ${String(e).slice(0, 80)}`,
        finally: () => setPending(null),
      });
    },
    [qc, setOpen],
  );

  const wake = () => runAction("wake", "Waking tower", () => fetch("/api/tower/wake", { method: "POST" }).then((r) => r.json()));
  const sweep = () => runAction("sweep", "Sync sweep", () => fetch("/api/git/sync", { method: "POST" }).then((r) => r.json()));
  const refresh = () => runAction("refresh", "Refreshing telemetry", () => fetch("/api/dashboard?refresh=1").then((r) => r.json()));

  const exportCsv = () =>
    run(() => {
      window.location.assign("/api/journal?format=csv&csvLimit=1000");
      toast.success("Journal export started (CSV, max 1000 rows)");
    });

  const toggleWatchdog = () =>
    runAction(
      "watchdog",
      "Toggling service watchdog",
      async () => {
        const s = await fetch("/api/settings", { cache: "no-store" }).then((r) => r.json());
        const next = !(s?.watchdogEnabled === true);
        return fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ watchdogEnabled: next }),
        }).then((r) => r.json());
      },
    );

  const copyDiagnostics = () =>
    run(async () => {
      const [dash, git] = await Promise.all([
        fetch("/api/dashboard", { cache: "no-store" }).then((r) => r.json()).catch(() => null),
        fetch("/api/git/status", { cache: "no-store" }).then((r) => r.json()).catch(() => null),
      ]);
      const diag = {
        exportedAt: new Date().toISOString(),
        tower: dash?.tower,
        services: dash?.services?.map((s: { provider: string; status: string; latencyMs: number | null }) => ({ provider: s.provider, status: s.status, latencyMs: s.latencyMs })),
        git: git ? { branch: git.trackedBranch ?? git.branch, mainHead: git.mainHeadSha, openPrs: git.prs?.length ?? 0 } : null,
      };
      await navigator.clipboard
        .writeText(JSON.stringify(diag, null, 2))
        .then(() => toast.success("Diagnostics copied — paste anywhere"))
        .catch(() => toast.error("Clipboard unavailable in this context"));
    });

  const run = React.useCallback(
    (fn: () => void) => {
      setOpen(false);
      setTimeout(fn, 60);
    },
    [setOpen],
  );

  return (
    <CommandDialog open={open} onOpenChange={setOpen} aria-label="Command palette">
      <CommandInput placeholder="Type a command or search… (wake, sync, memory…)" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigate">
          {TABS.map((t) => (
            <CommandItem key={t.id} value={`go ${t.label}`} onSelect={() => navigate(t.id)}>
              {TAB_ICONS[t.id]}
              <span className="ml-2">{t.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Quick actions">
          <CommandItem value="wake tower" onSelect={() => run(wake)}>
            <Zap className="h-4 w-4" />
            <span className="ml-2">Wake Tower</span>
            <span className="ml-auto text-[10px] text-muted-foreground">POST /api/tower/wake</span>
          </CommandItem>
          <CommandItem value="run sync sweep" onSelect={() => run(sweep)}>
            <GitMerge className="h-4 w-4" />
            <span className="ml-2">Run Sync Sweep</span>
            <span className="ml-auto text-[10px] text-muted-foreground">PR ↔ main</span>
          </CommandItem>
          <CommandItem value="refresh telemetry" onSelect={() => run(refresh)}>
            <RefreshCw className="h-4 w-4" />
            <span className="ml-2">Force refresh telemetry</span>
          </CommandItem>
          <CommandItem value="export journal csv" onSelect={exportCsv}>
            <Download className="h-4 w-4" />
            <span className="ml-2">Export journal as CSV</span>
            <span className="ml-auto text-[10px] text-muted-foreground">≤1000 rows</span>
          </CommandItem>
          <CommandItem value="toggle service watchdog" onSelect={() => run(toggleWatchdog)}>
            <ShieldAlert className="h-4 w-4" />
            <span className="ml-2">Toggle service watchdog</span>
            <span className="ml-auto text-[10px] text-muted-foreground">transition alerts</span>
          </CommandItem>
          <CommandItem
            value="copy diagnostics snapshot"
            onSelect={copyDiagnostics}
          >
            <ClipboardCopy className="h-4 w-4" />
            <span className="ml-2">Copy diagnostics to clipboard</span>
            <span className="ml-auto text-[10px] text-muted-foreground">tower + fleet JSON</span>
          </CommandItem>
          <CommandItem
            value="toggle theme"
            onSelect={() =>
              run(() => {
                setTheme(theme === "dark" ? "light" : "dark");
                toast(`Theme → ${theme === "dark" ? "light" : "dark"}`);
              })
            }
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span className="ml-2">Toggle theme</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Platform">
          <CommandItem
            value="open github pull requests"
            onSelect={() =>
              run(async () => {
                const s = await fetch("/api/settings", { cache: "no-store" }).then((r) => r.json()).catch(() => null);
                const repo = s?.githubRepo || process.env.NEXT_PUBLIC_GITHUB_REPO || "SaifulHaqueNiloy/supremeai";
                window.open(`https://github.com/${repo}/pulls`, "_blank");
              })
            }
          >
            <ExternalLink className="h-4 w-4" />
            <span className="ml-2">Open GitHub Pull Requests</span>
          </CommandItem>
          <CommandItem
            value="open central tower health"
            onSelect={() =>
              run(async () => {
                const s = await fetch("/api/settings", { cache: "no-store" }).then((r) => r.json()).catch(() => null);
                if (!s?.towerUrl) {
                  toast.error("Tower URL not configured — set it in Settings");
                  return;
                }
                window.open(`${s.towerUrl}/health`, "_blank");
              })
            }
          >
            <RadioTower className="h-4 w-4" />
            <span className="ml-2">Tower health endpoint</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
      <div
        className="flex items-center justify-between border-t px-3 py-2 text-[10px] text-muted-foreground"
        aria-hidden
      >
        <span className="flex gap-3">
          <span><kbd className="rounded border bg-muted px-1 font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="rounded border bg-muted px-1 font-mono">↵</kbd> run</span>
          <span><kbd className="rounded border bg-muted px-1 font-mono">esc</kbd> close</span>
        </span>
        <span className="font-mono">mission control · v1.9</span>
      </div>
    </CommandDialog>
  );
}
