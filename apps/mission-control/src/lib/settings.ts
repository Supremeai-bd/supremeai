import { db } from "@/lib/db";

/** Dynamic settings (Dynamic by Design) — DB-backed with sane defaults. */

export const SETTING_DEFAULTS: Record<string, string> = {
  towerUrl: "https://supremeai-mcp-tower.onrender.com",
  towerKey: "supremeai_mcp_admin_88f1a2b3c4d5e6f7",
  githubRepo: "SaifulHaqueNiloy/supremeai",
  githubToken: "", // falls back to env GITHUB_TOKEN
  watchBranch: "main",
  autoWake: "true",
  autoSyncPrs: "true",
  refreshIntervalSec: "30",
  theme: "dark",
};

export async function getSettings(): Promise<Record<string, string>> {
  const out: Record<string, string> = { ...SETTING_DEFAULTS };
  try {
    const rows = await db.setting.findMany();
    for (const r of rows) if (r.value !== "") out[r.key] = r.value;
    if (!out.githubToken && process.env.GITHUB_TOKEN) out.githubToken = process.env.GITHUB_TOKEN;
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
