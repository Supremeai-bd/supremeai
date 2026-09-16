import { NextResponse } from "next/server";
import { getSettings, setSettings, maskKey } from "@/lib/settings";
import { parseWatchdogOverrides } from "@/lib/watchdog";
import type { SettingsData } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

export async function GET() {
  const s = await getSettings();
  const data: SettingsData = {
    towerUrl: s.towerUrl,
    towerKeyMasked: maskKey(s.towerKey),
    githubTokenMasked: maskKey(s.githubToken),
    githubRepo: s.githubRepo,
    watchBranch: s.watchBranch,
    renderAccountId: s.renderAccountId,
    autoWake: s.autoWake === "true",
    autoSyncPrs: s.autoSyncPrs === "true",
    refreshIntervalSec: Number(s.refreshIntervalSec) || 30,
    journalRetentionDays: Number(s.journalRetentionDays) || 14,
    watchdogEnabled: s.watchdogEnabled !== "false",
    watchdogNotifyChannel: (s.watchdogNotifyChannel as SettingsData["watchdogNotifyChannel"]) || "none",
    watchdogCooldownMin: Number(s.watchdogCooldownMin) || 15,
    watchdogOverrides: JSON.stringify(parseWatchdogOverrides(s.watchdogOverrides)),
    theme: (s.theme as SettingsData["theme"]) || "dark",
  };
  return NextResponse.json(data);
}

export async function PUT(request: Request) {
  const body = (await request.json().catch(() => null)) as Partial<{
    towerUrl: string;
    towerKey: string; // only updated when a non-masked new value arrives
    githubToken: string; // rotate-only — masked values are ignored
    githubRepo: string;
    watchBranch: string;
    renderAccountId: string;
    autoWake: boolean;
    autoSyncPrs: boolean;
    refreshIntervalSec: number;
    journalRetentionDays: number;
    watchdogEnabled: boolean;
    watchdogNotifyChannel: SettingsData["watchdogNotifyChannel"];
    watchdogCooldownMin: number;
    watchdogOverrides: string; // JSON — validated & normalized server-side
    theme: "dark" | "light" | "system";
  }> | null;
  if (!body) return NextResponse.json({ error: "Invalid body" }, { status: 400 });

  const updates: Record<string, string> = {};
  if (body.towerUrl) updates.towerUrl = body.towerUrl.trim().replace(/\/+$/, "");
  if (body.towerKey && !body.towerKey.includes("••")) updates.towerKey = body.towerKey.trim();
  if (body.githubToken && !body.githubToken.includes("••")) updates.githubToken = body.githubToken.trim();
  if (body.githubRepo) updates.githubRepo = body.githubRepo.trim();
  if (body.watchBranch) updates.watchBranch = body.watchBranch.trim();
  if (body.renderAccountId) updates.renderAccountId = body.renderAccountId.trim();
  if (typeof body.autoWake === "boolean") updates.autoWake = String(body.autoWake);
  if (typeof body.autoSyncPrs === "boolean") updates.autoSyncPrs = String(body.autoSyncPrs);
  if (typeof body.refreshIntervalSec === "number" && body.refreshIntervalSec >= 10 && body.refreshIntervalSec <= 600)
    updates.refreshIntervalSec = String(Math.floor(body.refreshIntervalSec));
  if (typeof body.journalRetentionDays === "number" && body.journalRetentionDays >= 1 && body.journalRetentionDays <= 365)
    updates.journalRetentionDays = String(Math.floor(body.journalRetentionDays));
  if (typeof body.watchdogEnabled === "boolean") updates.watchdogEnabled = String(body.watchdogEnabled);
  if (body.watchdogNotifyChannel && ["none", "telegram", "discord"].includes(body.watchdogNotifyChannel))
    updates.watchdogNotifyChannel = body.watchdogNotifyChannel;
  if (typeof body.watchdogCooldownMin === "number" && body.watchdogCooldownMin >= 0 && body.watchdogCooldownMin <= 240)
    updates.watchdogCooldownMin = String(Math.floor(body.watchdogCooldownMin));
  if (typeof body.watchdogOverrides === "string" && body.watchdogOverrides.length <= 4000)
    updates.watchdogOverrides = JSON.stringify(parseWatchdogOverrides(body.watchdogOverrides)); // normalize or reset to {}
  if (body.theme && ["dark", "light", "system"].includes(body.theme)) updates.theme = body.theme;

  await setSettings(updates);
  const s = await getSettings();
  const data: SettingsData = {
    towerUrl: s.towerUrl,
    towerKeyMasked: maskKey(s.towerKey),
    githubTokenMasked: maskKey(s.githubToken),
    githubRepo: s.githubRepo,
    watchBranch: s.watchBranch,
    renderAccountId: s.renderAccountId,
    autoWake: s.autoWake === "true",
    autoSyncPrs: s.autoSyncPrs === "true",
    refreshIntervalSec: Number(s.refreshIntervalSec) || 30,
    journalRetentionDays: Number(s.journalRetentionDays) || 14,
    watchdogEnabled: s.watchdogEnabled !== "false",
    watchdogNotifyChannel: (s.watchdogNotifyChannel as SettingsData["watchdogNotifyChannel"]) || "none",
    watchdogCooldownMin: Number(s.watchdogCooldownMin) || 15,
    watchdogOverrides: JSON.stringify(parseWatchdogOverrides(s.watchdogOverrides)),
    theme: (s.theme as SettingsData["theme"]) || "dark",
  };
  return NextResponse.json(data);
}
