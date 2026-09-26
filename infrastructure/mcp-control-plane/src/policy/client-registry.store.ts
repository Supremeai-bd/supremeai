import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { buildAccountChain } from "../lib/redis_chain.js";

export interface PersistedClientRecord {
  id: string;
  tenantId?: string;
  name: string;
  provider: string;
  protocol: string;
  role: string;
  scopes: string[];
  createdAt: string;
  updatedAt: string;
  expiresAt?: string;
  lastSeenAt?: string;
  status: string;
  tokenHash: string;
}

export interface ClientRegistryStore {
  /** Short backend identifier for boot logs (e.g. "memory", "file", "upstash-chain"). */
  readonly backend: string;
  /** Synchronous snapshot read (memory/file: authoritative; upstash: last-known). */
  load(): PersistedClientRecord[];
  /** Optional async hydration for network-backed stores (called once at boot). */
  loadAsync?(): Promise<PersistedClientRecord[]>;
  save(records: PersistedClientRecord[]): void;
}

export class MemoryClientRegistryStore implements ClientRegistryStore {
  readonly backend = "memory";
  private records: PersistedClientRecord[] = [];

  load(): PersistedClientRecord[] {
    return this.records.map((record) => ({ ...record, scopes: [...record.scopes] }));
  }

  save(records: PersistedClientRecord[]): void {
    this.records = records.map((record) => ({ ...record, scopes: [...record.scopes] }));
  }
}

export class JsonFileClientRegistryStore implements ClientRegistryStore {
  readonly backend = "file";

  constructor(private readonly filePath: string) {}

  load(): PersistedClientRecord[] {
    if (!existsSync(this.filePath)) return [];
    const parsed: unknown = JSON.parse(readFileSync(this.filePath, "utf8"));
    if (!Array.isArray(parsed)) throw new Error("MCP client registry must contain an array");
    return parsed as PersistedClientRecord[];
  }

  save(records: PersistedClientRecord[]): void {
    mkdirSync(dirname(this.filePath), { recursive: true });
    const temporaryPath = `${this.filePath}.tmp`;
    writeFileSync(temporaryPath, `${JSON.stringify(records, null, 2)}\n`, { mode: 0o600 });
    renameSync(temporaryPath, this.filePath);
  }
}

/**
 * Upstash-backed client registry (#1421) — survives tower redeploys AND
 * instance restarts by storing the registry as one JSON document on the
 * existing multi-account chain (primary → secondary → … → quinary, same
 * accounts the agent heartbeats use).
 *
 * Write path: every `save()` updates the in-process snapshot immediately and
 * schedules a debounced flush to ALL reachable accounts (best-effort each).
 * The debounce is quota-aware (#1438): stable mutations (register/approve/
 * revoke/rotate/role) flush after 5s; volatile-only changes (resolveClient's
 * lastSeenAt bumps on every authenticated call) flush at most every 5 minutes.
 * Read path: `loadAsync()` at boot walks the chain and takes the first
 * reachable account's copy; `load()` returns the last-known snapshot.
 */
export class UpstashClientRegistryStore implements ClientRegistryStore {
  readonly backend = "upstash-chain";

  private static readonly STABLE_FLUSH_MS = 5_000;
  private static readonly VOLATILE_FLUSH_MS = 300_000;
  private static readonly REST_TIMEOUT_MS = 10_000;

  private snapshot: PersistedClientRecord[] = [];
  private lastStableJson = "";
  private flushTimer: NodeJS.Timeout | null = null;
  private flushing = false;
  private flushQueuedAgain = false;

  constructor(private readonly key: string = process.env.MCP_CLIENT_REGISTRY_KEY || "supremeai:mcp:client-registry") {}

  /** Lazy chain construction — env may be injected after import (Infisical pull in main()). */
  private chain() {
    return buildAccountChain().filter((account) => account.restUrl && account.restToken);
  }

  private async restCall(restUrl: string, restToken: string, command: unknown[]): Promise<unknown> {
    const res = await fetch(restUrl, {
      method: "POST",
      headers: { Authorization: `Bearer ${restToken}`, "Content-Type": "application/json" },
      body: JSON.stringify(command),
      signal: AbortSignal.timeout(UpstashClientRegistryStore.REST_TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`Upstash REST returned HTTP ${res.status}`);
    const payload = (await res.json()) as { result?: unknown; error?: string };
    if (payload.error) throw new Error(`Upstash error: ${payload.error}`);
    return payload.result;
  }

  load(): PersistedClientRecord[] {
    return this.snapshot.map((record) => ({ ...record, scopes: [...record.scopes] }));
  }

  async loadAsync(): Promise<PersistedClientRecord[]> {
    const chain = this.chain();
    const errors: string[] = [];
    for (const account of chain) {
      try {
        const result = await this.restCall(account.restUrl as string, account.restToken as string, ["GET", this.key]);
        if (result == null) return []; // reachable account, fresh registry — nothing stored yet
        const parsed: unknown = JSON.parse(String(result));
        if (!Array.isArray(parsed)) throw new Error("stored registry is not an array");
        this.snapshot = parsed as PersistedClientRecord[];
        this.lastStableJson = stableJson(this.snapshot);
        return this.load();
      } catch (err) {
        errors.push(`${account.label}: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    if (chain.length > 0) {
      console.error(`[client-registry] hydration failed on all ${chain.length} chain account(s): ${errors.join(" | ")}`);
    }
    return [];
  }

  save(records: PersistedClientRecord[]): void {
    this.snapshot = records.map((record) => ({ ...record, scopes: [...record.scopes] }));
    const stable = stableJson(this.snapshot);
    const stableChanged = stable !== this.lastStableJson;
    if (stableChanged) this.lastStableJson = stable;
    // Stable mutations flush fast; lastSeenAt-only churn flushes on the slow cadence.
    this.scheduleFlush(stableChanged ? UpstashClientRegistryStore.STABLE_FLUSH_MS : UpstashClientRegistryStore.VOLATILE_FLUSH_MS);
  }

  private scheduleFlush(delayMs: number): void {
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      void this.flush();
    }, delayMs);
    this.flushTimer.unref?.();
  }

  private async flush(): Promise<void> {
    if (this.flushing) { this.flushQueuedAgain = true; return; }
    this.flushing = true;
    try {
      do {
        this.flushQueuedAgain = false;
        const chain = this.chain();
        if (chain.length === 0) return;
        const body = JSON.stringify(this.snapshot);
        const results = await Promise.allSettled(
          chain.map((account) =>
            this.restCall(account.restUrl as string, account.restToken as string, ["SET", this.key, body]),
          ),
        );
        const failures = results
          .map((r, i) => (r.status === "rejected" ? `${chain[i].label}: ${String(r.reason)}` : null))
          .filter(Boolean);
        if (failures.length > 0) {
          console.error(`[client-registry] flush partial failure (${failures.length}/${chain.length}): ${failures.join(" | ")}`);
        }
      } while (this.flushQueuedAgain);
    } finally {
      this.flushing = false;
    }
  }
}

/** lastSeenAt is volatile (bumped on every authenticated resolve) — excluded from change detection. */
function stableJson(records: PersistedClientRecord[]): string {
  return JSON.stringify(records.map(({ lastSeenAt: _lastSeenAt, ...rest }) => rest));
}

export function createClientRegistryStore(filePath?: string): ClientRegistryStore {
  if (filePath) return new JsonFileClientRegistryStore(filePath);
  return new UpstashClientRegistryStore();
}
