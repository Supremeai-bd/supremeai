"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bot,
  Brain,
  ExternalLink,
  GitMerge,
  LayoutDashboard,
  Moon,
  RadioTower,
  RefreshCw,
  Settings2,
  Sun,
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
              run(() => window.open("https://github.com/SaifulHaqueNiloy/supremeai/pulls", "_blank"))
            }
          >
            <ExternalLink className="h-4 w-4" />
            <span className="ml-2">Open GitHub Pull Requests</span>
          </CommandItem>
          <CommandItem
            value="open central tower health"
            onSelect={() => run(() => window.open("https://supremeai-mcp-tower.onrender.com/health", "_blank"))}
          >
            <RadioTower className="h-4 w-4" />
            <span className="ml-2">Tower health endpoint</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
