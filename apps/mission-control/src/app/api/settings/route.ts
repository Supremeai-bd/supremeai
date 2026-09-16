import { NextResponse } from "next/server";
import { getSettings, setSettings, maskKey } from "@/lib/settings";
import type { SettingsData } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

export async function GET() {
  const s = await getSettings();
  const data: SettingsData = {
    towerUrl: s.towerUrl,
    towerKeyMasked: maskKey(s.towerKey),
    githubRepo: s.githubRepo,
    watchBranch: s.watchBranch,
    autoWake: s.autoWake === "true",
    autoSyncPrs: s.autoSyncPrs === "true",
    refreshIntervalSec: Number(s.refreshIntervalSec) || 30,
    theme: (s.theme as SettingsData["theme"]) || "dark",
  };
  return NextResponse.json(data);
}

export async function PUT(request: Request) {
  const body = (await request.json().catch(() => null)) as Partial<{
    towerUrl: string;
    towerKey: string; // only updated when a non-masked new value arrives
    githubRepo: string;
    watchBranch: string;
    autoWake: boolean;
    autoSyncPrs: boolean;
    refreshIntervalSec: number;
    theme: "dark" | "light" | "system";
  }> | null;
  if (!body) return NextResponse.json({ error: "Invalid body" }, { status: 400 });

  const updates: Record<string, string> = {};
  if (body.towerUrl) updates.towerUrl = body.towerUrl.trim().replace(/\/+$/, "");
  if (body.towerKey && !body.towerKey.includes("••")) updates.towerKey = body.towerKey.trim();
  if (body.githubRepo) updates.githubRepo = body.githubRepo.trim();
  if (body.watchBranch) updates.watchBranch = body.watchBranch.trim();
  if (typeof body.autoWake === "boolean") updates.autoWake = String(body.autoWake);
  if (typeof body.autoSyncPrs === "boolean") updates.autoSyncPrs = String(body.autoSyncPrs);
  if (typeof body.refreshIntervalSec === "number" && body.refreshIntervalSec >= 10 && body.refreshIntervalSec <= 600)
    updates.refreshIntervalSec = String(Math.floor(body.refreshIntervalSec));
  if (body.theme && ["dark", "light", "system"].includes(body.theme)) updates.theme = body.theme;

  await setSettings(updates);
  const s = await getSettings();
  const data: SettingsData = {
    towerUrl: s.towerUrl,
    towerKeyMasked: maskKey(s.towerKey),
    githubRepo: s.githubRepo,
    watchBranch: s.watchBranch,
    autoWake: s.autoWake === "true",
    autoSyncPrs: s.autoSyncPrs === "true",
    refreshIntervalSec: Number(s.refreshIntervalSec) || 30,
    theme: (s.theme as SettingsData["theme"]) || "dark",
  };
  return NextResponse.json(data);
}
