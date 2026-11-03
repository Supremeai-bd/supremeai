// Shared types for SupremeAI Mission Control APIs

export type TowerStatus = "live" | "sleeping" | "degraded" | "unreachable" | "unknown";

export interface TowerHealth {
  status: TowerStatus;
  latencyMs: number | null;
  version: string | null;
  serverName: string | null;
  toolsCount: number;
  checkedAt: string;
  wakeAttempts: number;
  detail?: string;
}

export interface ServiceStatus {
  provider: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latencyMs: number | null;
  checkedAt: string;
  note?: string;
}

export interface DashboardData {
  tower: TowerHealth;
  services: ServiceStatus[];
  summary: string | null;
  toolsCount: number;
  /** Real open-PR count from the GitHub API; null = GitHub unconfigured/API error. */
  openPrs: number | null;
  activity: ActivityItem[];
  updatedAt: string;
}

export interface ActivityItem {
  id: string;
  type: string;
  level: string;
  title: string;
  detail: string | null;
  createdAt: string;
}

export interface McpToolInfo {
  name: string;
  description: string;
  inputSchema: unknown;
  category: string;
}

export interface ToolCallResult {
  ok: boolean;
  tool: string;
  durationMs: number;
  result: unknown;
  error?: string;
}

export interface PullRequestInfo {
  number: number;
  title: string;
  branch: string;
  base: string;
  state: string;
  merged: boolean;
  draft: boolean;
  mergeable: "mergeable" | "conflicting" | "unknown";
  behindBy: number;
  aheadBy: number;
  updatedAt: string;
  url: string;
  ciStatus: string | null;
}

export interface GitStatusData {
  /** Watch branch from dynamic settings (fallback display). */
  branch: string;
  /** Head branch of the primary open PR we track (null when none open). */
  trackedBranch: string | null;
  defaultBranch: string;
  mainHeadSha: string;
  prs: PullRequestInfo[];
  branches: { name: string; sha: string; protected: boolean }[];
  checkedAt: string;
}

export interface GitSyncResult {
  ok: boolean;
  action: "checked" | "synced_main" | "pr_merged" | "skipped" | "error";
  message: string;
  prNumber?: number;
  behindBy?: number;
  conflict?: string;
}

export interface MemoryNoteData {
  id: string;
  kind: string;
  title: string;
  content: string;
  tags: string[];
  source: string;
  pinned: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SettingsData {
  towerUrl: string;
  towerKeyMasked: string;
  /** Masked GitHub PAT (rotate-only via PUT body field `githubToken`). */
  githubTokenMasked: string;
  githubRepo: string;
  watchBranch: string;
  renderAccountId: string;
  autoWake: boolean;
  autoSyncPrs: boolean;
  refreshIntervalSec: number;
  journalRetentionDays: number;
  watchdogEnabled: boolean;
  watchdogNotifyChannel: "none" | "telegram" | "discord";
  watchdogCooldownMin: number;
  /** Per-provider watchdog overrides — JSON string (Dynamic by Design). */
  watchdogOverrides: string;
  theme: "dark" | "light" | "system";
}
