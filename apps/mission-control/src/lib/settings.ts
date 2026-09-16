import { db } from "@/lib/db";

/** Dynamic settings (Dynamic by Design) — DB-backed with sane defaults. */

export const SETTING_DEFAULTS: Record<string, string> = {
  // Zero-hardcode policy: deployment URLs & secrets NEVER live in source.
  // Resolution order: DB setting → environment (TOWER_URL / TOWER_ADMIN_KEY).
  towerUrl: "",
  towerKey: "",
  githubRepo: "SaifulHaqueNiloy/supremeai",
  githubToken: "", // falls back to env GITHUB_TOKEN
  watchBranch: "main",
  renderAccountId: "render-primary", // tower resource id for the Render fleet
  autoWake: "true",
  autoSyncPrs: "true",
  refreshIntervalSec: "30",
  journalRetentionDays: "14", // ToolCallLog pruning window (dynamic)
  watchdogEnabled: "true", // service transition alerts (dynamic)
  watchdogNotifyChannel: "none", // none | telegram | discord (tower notify tools)
  watchdogCooldownMin: "15", // per-provider alert suppression window
  watchdogOverrides: "{}", // per-provider JSON overrides: mute / custom cooldown / channel
  theme: "dark",
};

export async function getSettings(): Promise<Record<string, string>> {
  const out: Record<string, string> = { ...SETTING_DEFAULTS };
  try {
    const rows = await db.setting.findMany();
    for (const r of rows) if (r.value !== "") out[r.key] = r.value;
    if (!out.githubToken && process.env.GITHUB_TOKEN) out.githubToken = process.env.GITHUB_TOKEN;
    if (!out.towerUrl && process.env.TOWER_URL) out.towerUrl = process.env.TOWER_URL;
    if (!out.towerKey && process.env.TOWER_ADMIN_KEY) out.towerKey = process.env.TOWER_ADMIN_KEY;
  } catch {
    /* DB not ready */
  }
  return out;
}

export async function setSetting(key: string, value: string): Promise<void> {
  await db.setting.upsert({
    where: { key },
    update: { value },
    create: { key, value },
  });
}

export async function setSettings(values: Record<string, string>): Promise<void> {
  for (const [k, v] of Object.entries(values)) await setSetting(k, v);
}

export function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 10) return "••••••••";
  return `${key.slice(0, 6)}••••••••${key.slice(-4)}`;
}

export async function logActivity(type: string, level: string, title: string, detail?: string, meta?: unknown): Promise<void> {
  try {
    await db.activityEvent.create({
      data: {
        type,
        level,
        title,
        detail: detail ?? null,
        meta: meta ? JSON.stringify(meta) : null,
      },
    });
  } catch {
    /* never crash on logging */
  }
}
