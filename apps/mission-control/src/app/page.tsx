"use client";

import * as React from "react";
import { DashboardTab } from "@/components/mission-control/dashboard-tab";
import { TowerTab } from "@/components/mission-control/tower-tab";
import { GitTab } from "@/components/mission-control/git-tab";
import { BrainTab } from "@/components/mission-control/brain-tab";
import { AutonomyTab } from "@/components/mission-control/autonomy-tab";
import { SettingsTab } from "@/components/mission-control/settings-tab";
import { Footer, Header, TabShell, type TabId } from "@/components/mission-control/shell";

const VALID: TabId[] = ["dashboard", "tower", "git", "brain", "autonomy", "settings"];

export default function MissionControlPage() {
  const [tab, setTab] = React.useState<TabId>("dashboard");

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
    return () => {
      window.removeEventListener("hashchange", fromHash);
      window.removeEventListener("mc-navigate", onNav);
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
        {tab === "settings" && <SettingsTab />}
      </TabShell>
      <Footer />
    </div>
  );
}
