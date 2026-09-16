import { db } from "@/lib/db";
import { getSettings, logActivity } from "@/lib/settings";
import { callTowerTool } from "@/lib/tower-client";
import type { ServiceStatus } from "@/lib/mission-types";

/**
 * Service-down watchdog — dynamic, zero-cost reliability alerting.
 *
 * Runs inside GET /api/dashboard on every refresh: compares fresh tower
 * service statuses against the latest local ServiceSnapshot per provider,
 * detects transitions (down/degraded/recovered) and:
 *   1. writes an ActivityEvent (visible in the Activity Stream + dashboard)
 *   2. optionally broadcasts via the tower notify channel (dynamic setting,
 *      best-effort — tower asleep or missing chat id never breaks the dashboard)
 *
 * Cooldown (dynamic, watchdogCooldownMin) prevents alert storms: repeated
 * notifications for the same provider+kind are suppressed, but every
 * transition is still recorded as an event for the audit trail.
 */

export interface ServiceTransition {
  provider: string;
  from: ServiceStatus["status"];
  to: ServiceStatus["status"];
  kind: "down" | "degraded" | "recovered";
  note: string | null;
}

/** Channels the tower exposes for operator notifications. */
export const NOTIFY_CHANNELS = ["none", "telegram", "discord"] as const;
export type NotifyChannel = (typeof NOTIFY_CHANNELS)[number];

/**
 * Per-provider watchdog overrides (dynamic setting `watchdogOverrides`, JSON).
 * Lets the operator mute noisy providers, give them a custom cooldown, or a
 * dedicated notify channel — without touching code. Example:
 *   {"cloudflare":{"enabled":false},"render":{"cooldownMin":60,"channel":"discord"}}
 */
export interface WatchdogOverride {
  enabled?: boolean;
  cooldownMin?: number;
  channel?: NotifyChannel;
}
export type WatchdogOverridesMap = Record<string, WatchdogOverride>;

/** Defensive parser: never throws, always returns a valid map (≤64 providers). */
export function parseWatchdogOverrides(raw: string | undefined | null): WatchdogOverridesMap {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: WatchdogOverridesMap = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>).slice(0, 64)) {
      if (!v || typeof v !== "object" || Array.isArray(v)) continue;
      const r = v as Record<string, unknown>;
      const o: WatchdogOverride = {};
      if (typeof r.enabled === "boolean") o.enabled = r.enabled;
      if (typeof r.cooldownMin === "number" && r.cooldownMin >= 0 && r.cooldownMin <= 240)
        o.cooldownMin = Math.floor(r.cooldownMin);
      if (typeof r.channel === "string" && (NOTIFY_CHANNELS as readonly string[]).includes(r.channel))
        o.channel = r.channel as NotifyChannel;
      if (Object.keys(o).length > 0) out[k.trim().toLowerCase()] = o;
    }
    return out;
  } catch {
    return {};
  }
}

/**
 * Match an override key against a provider name — case-insensitive and
 * prefix-aware, because tower provider names are descriptive
 * ("Cloudflare (DNS + Workers + Analytics)") while operators type short
 * keys ("cloudflare"). An exact match always wins via map iteration order
 * only if listed first; prefix matches are accepted for convenience.
 */
export function overrideMatches(key: string, provider: string): boolean {
  const k = key.trim().toLowerCase();
  const p = provider.trim().toLowerCase();
  return p === k || p.startsWith(k);
}

function overrideFor(map: WatchdogOverridesMap, provider: string): WatchdogOverride | undefined {
  for (const [key, ov] of Object.entries(map)) {
    if (overrideMatches(key, provider)) return ov;
  }
  return undefined;
}

async function latestSnapshotStatus(provider: string): Promise<string | null> {
  const snap = await db.serviceSnapshot.findFirst({
    where: { provider },
    orderBy: { checkedAt: "desc" },
    select: { status: true },
  });
  return snap?.status ?? null;
}

async function recentlyAlerted(provider: string, kind: string, cooldownMin: number): Promise<boolean> {
  if (cooldownMin <= 0) return false;
  // Only actual notify events count toward cooldown — transition journal entries
  // (which share provider/kind meta) must never suppress their own notify.
  const recent = await db.activityEvent.findMany({
    where: { type: "watchdog", createdAt: { gte: new Date(Date.now() - cooldownMin * 60_000) } },
    orderBy: { createdAt: "desc" },
    select: { meta: true },
    take: 20,
  });
  return recent.some((r) => {
    try {
      const meta = JSON.parse(r.meta ?? "") as { provider?: string; kind?: string; notified?: boolean };
      return meta.notified === true && meta.provider === provider && meta.kind === kind;
    } catch {
      return false;
    }
  });
}

/** Detect transitions BEFORE new snapshots are persisted. */
export async function detectServiceTransitions(services: ServiceStatus[]): Promise<ServiceTransition[]> {
  const transitions: ServiceTransition[] = [];
  for (const s of services.slice(0, 12)) {
    if (s.status === "unknown") continue;
    if (s.note === "cached") continue; // cached fallback isn't fresh evidence
    const prev = await latestSnapshotStatus(s.provider).catch(() => null);
    if (!prev || prev === s.status) continue;
    const kind: ServiceTransition["kind"] =
      s.status === "down" ? "down" : s.status === "degraded" ? "degraded" : prev === "down" || prev === "degraded" ? "recovered" : "recovered";
    transitions.push({ provider: s.provider, from: prev as ServiceStatus["status"], to: s.status, kind, note: s.note ?? null });
  }
  return transitions;
}

/**
 * Operator drill — simulate a DOWN transition for a provider to verify the
 * full watchdog path (journal entry + tower broadcast) without waiting for a
 * real outage. No snapshot is written and no real status changes: the drill
 * is purely a journaled, clearly-labeled test event. Drills bypass cooldown
 * (explicit operator action) but still respect mute overrides and require the
 * watchdog to be armed.
 */
export async function runWatchdogDrill(
  provider: string,
): Promise<{ journaled: boolean; notified: boolean | null; channel: NotifyChannel; error?: string }> {
  const name = provider.trim();
  if (!name || name.length > 80) return { journaled: false, notified: null, channel: "none", error: "invalid provider name" };

  let settings: Record<string, string>;
  try {
    settings = await getSettings();
  } catch (err) {
    return { journaled: false, notified: null, channel: "none", error: String(err).slice(0, 160) };
  }
  if (settings.watchdogEnabled === "false") {
    return { journaled: false, notified: null, channel: "none", error: "watchdog is disabled — arm it first" };
  }

  const overrides = parseWatchdogOverrides(settings.watchdogOverrides);
  const globalChannel = (settings.watchdogNotifyChannel ?? "none") as NotifyChannel;
  const ov = overrideFor(overrides, name);
  if (ov?.enabled === false) {
    return { journaled: false, notified: null, channel: "none", error: `"${name}" is muted by a per-provider override` };
  }
  const effChannel = ov?.channel ?? globalChannel;

  const nowUtc = new Date().toISOString().slice(11, 19);
  await logActivity(
    "watchdog",
    "warn",
    `Watchdog drill: ${name} simulated DOWN`,
    `drill · healthy → down · fired at ${nowUtc} UTC — no real status change`,
    { provider: name, kind: "down", drill: true, from: "healthy", to: "down" },
  ).catch(() => undefined);

  if (effChannel === "none") return { journaled: true, notified: null, channel: effChannel };

  const message = `🧪 SupremeAI watchdog DRILL: ${name} simulated DOWN (healthy → down) at ${nowUtc} UTC — test of the notify path, no action needed`;
  try {
    const tool = effChannel === "telegram" ? "notify_send_telegram" : "notify_send_discord";
    const res = await callTowerTool(tool, { message: message.slice(0, effChannel === "telegram" ? 4000 : 1900) });
    await logActivity(
      "watchdog",
      res.ok ? "success" : "warn",
      `Drill notify via ${effChannel} ${res.ok ? "sent" : "failed"}`,
      res.ok ? `${name} drill broadcast delivered` : (res.error ?? "tower rejected").slice(0, 200),
      { provider: name, kind: "down", drill: true, channel: effChannel, notified: res.ok },
    ).catch(() => undefined);
    return { journaled: true, notified: res.ok, channel: effChannel, error: res.ok ? undefined : (res.error ?? "tower rejected").slice(0, 160) };
  } catch (err) {
    await logActivity("watchdog", "warn", `Drill notify via ${effChannel} errored`, String(err).slice(0, 200), {
      provider: name,
      kind: "down",
      drill: true,
      channel: effChannel,
      notified: false,
    }).catch(() => undefined);
    return { journaled: true, notified: false, channel: effChannel, error: String(err).slice(0, 160) };
  }
}

/** Handle transitions: journal + optional tower broadcast. Never throws. */
export async function handleServiceTransitions(transitions: ServiceTransition[]): Promise<void> {
  if (transitions.length === 0) return;
  let settings: Record<string, string>;
  try {
    settings = await getSettings();
  } catch {
    return;
  }
  if (settings.watchdogEnabled === "false") return;

  const overrides = parseWatchdogOverrides(settings.watchdogOverrides);
  const channel = (settings.watchdogNotifyChannel ?? "none") as NotifyChannel;
  const cooldownMin = Math.max(0, Math.min(240, Number(settings.watchdogCooldownMin) || 15));

  for (const t of transitions) {
    // Per-provider override wins over global defaults (mute / custom cooldown / channel)
    const ov = overrideFor(overrides, t.provider);
    if (ov?.enabled === false) continue; // muted provider — skip entirely
    const effChannel = ov?.channel ?? channel;
    const effCooldown = ov?.cooldownMin ?? cooldownMin;

    const icon = t.kind === "down" ? "🔴" : t.kind === "degraded" ? "🟠" : "🟢";
    const title =
      t.kind === "down"
        ? `Watchdog: ${t.provider} is DOWN`
        : t.kind === "degraded"
          ? `Watchdog: ${t.provider} degraded`
          : `Watchdog: ${t.provider} recovered`;
    const detail = `${t.from} → ${t.to}${t.note ? ` · ${t.note}` : ""}`;

    // Always journal the transition (audit trail even when notify is off/cooled)
    await logActivity("watchdog", t.kind === "down" ? "error" : t.kind === "degraded" ? "warn" : "success", title, detail, {
      provider: t.provider,
      kind: t.kind,
      from: t.from,
      to: t.to,
    }).catch(() => undefined);

    // Broadcast only for actionable transitions + cooldown window
    if (effChannel === "none" || t.kind === "recovered") continue;
    if (await recentlyAlerted(t.provider, t.kind, effCooldown)) continue;

    const message = `${icon} SupremeAI watchdog: ${t.provider} ${t.kind.toUpperCase()} (${t.from} → ${t.to}) at ${new Date().toISOString().slice(11, 19)} UTC${t.note ? ` — ${t.note}` : ""}`;
    try {
      const tool = effChannel === "telegram" ? "notify_send_telegram" : "notify_send_discord";
      const res = await callTowerTool(tool, { message: message.slice(0, effChannel === "telegram" ? 4000 : 1900) });
      await logActivity(
        "watchdog",
        res.ok ? "success" : "warn",
        `Watchdog notify via ${effChannel} ${res.ok ? "sent" : "failed"}`,
        res.ok ? `${t.provider} ${t.kind} broadcast delivered` : (res.error ?? "tower rejected").slice(0, 200),
        { provider: t.provider, kind: t.kind, channel: effChannel, notified: res.ok },
      ).catch(() => undefined);
    } catch (err) {
      await logActivity("watchdog", "warn", `Watchdog notify via ${effChannel} errored`, String(err).slice(0, 200), {
        provider: t.provider,
        kind: t.kind,
        channel: effChannel,
        notified: false,
      }).catch(() => undefined);
    }
  }
}
