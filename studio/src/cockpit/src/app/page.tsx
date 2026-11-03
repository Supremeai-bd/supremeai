"use client";

import * as React from "react";
import { DashboardTab } from "@/components/mission-control/dashboard-tab";
import { TowerTab } from "@/components/mission-control/tower-tab";
import { GitTab } from "@/components/mission-control/git-tab";
import { BrainTab } from "@/components/mission-control/brain-tab";
import { AutonomyTab } from "@/components/mission-control/autonomy-tab";
import { JournalTab } from "@/components/mission-control/journal-tab";
import { TenancyTab } from "@/components/mission-control/tenancy-tab";
import { SettingsTab } from "@/components/mission-control/settings-tab";
import { CommandPalette } from "@/components/mission-control/command-palette";
import { Footer, Header, TabShell, type TabId } from "@/components/mission-control/shell";

const VALID: TabId[] = ["dashboard", "tower", "git", "brain", "autonomy", "journal", "tenancy", "settings"];

export default function MissionControlPage() {
  const [tab, setTab] = React.useState<TabId>("dashboard");
  const [paletteOpen, setPaletteOpen] = React.useState(false);

  // Per-tab document title (usability + history readability)
  React.useEffect(() => {
    const label =
      tab === "git" ? "Git Sync"
      : tab === "tower" ? "Tower Explorer"
      : tab === "brain" ? "Brain & Memory"
      : tab === "journal" ? "Operations Journal"
      : tab === "tenancy" ? "Tenancy & Clients"
      : tab.charAt(0).toUpperCase() + tab.slice(1);
    document.title = `SupremeAI · ${label}`;
  }, [tab]);

  React.useEffect(() => {
    // Accept hash deep-links (#git) + header nav events
    const fromHash = () => {
      const h = window.location.hash.replace("#", "") as TabId;
      if (VALID.includes(h)) setTab(h);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    const onNav = (e: Event) => {
      const id = (e as CustomEvent<TabId>).detail;
      if (VALID.includes(id)) {
        setTab(id);
        history.replaceState(null, "", `#${id}`);
      }
    };
    window.addEventListener("mc-navigate", onNav);

    // ⌘K / Ctrl+K opens the command palette; header button fires mc-palette
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
      if (e.key === "/" && !["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName)) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    const onPalette = () => setPaletteOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mc-palette", onPalette);
    return () => {
      window.removeEventListener("hashchange", fromHash);
      window.removeEventListener("mc-navigate", onNav);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mc-palette", onPalette);
    };
  }, []);

  return (
    <div className="mc-grid-bg flex min-h-screen flex-col">
      <Header active={tab} />
      <TabShell active={tab}>
        {tab === "dashboard" && <DashboardTab onNavigate={(t) => setTab(t as TabId)} />}
        {tab === "tower" && <TowerTab />}
        {tab === "git" && <GitTab />}
        {tab === "brain" && <BrainTab />}
        {tab === "autonomy" && <AutonomyTab />}
        {tab === "journal" && <JournalTab />}
        {tab === "tenancy" && <TenancyTab />}
        {tab === "settings" && <SettingsTab />}
      </TabShell>
      <Footer />
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />
    </div>
  );
}
