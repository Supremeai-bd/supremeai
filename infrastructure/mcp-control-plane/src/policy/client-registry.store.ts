import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export interface PersistedClientRecord {
  id: string;
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
  load(): PersistedClientRecord[];
  save(records: PersistedClientRecord[]): void;
}

export class MemoryClientRegistryStore implements ClientRegistryStore {
  private records: PersistedClientRecord[] = [];

  load(): PersistedClientRecord[] {
    return this.records.map((record) => ({ ...record, scopes: [...record.scopes] }));
  }

  save(records: PersistedClientRecord[]): void {
    this.records = records.map((record) => ({ ...record, scopes: [...record.scopes] }));
  }
}

export class JsonFileClientRegistryStore implements ClientRegistryStore {
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

export function createClientRegistryStore(filePath?: string): ClientRegistryStore {
  return filePath ? new JsonFileClientRegistryStore(filePath) : new MemoryClientRegistryStore();
}
