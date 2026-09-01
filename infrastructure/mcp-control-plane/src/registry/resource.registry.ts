import { buildAccountRegistry, ProviderAccount } from "./account.registry.js";
import { Capability } from "./capability.registry.js";
import { ProviderName } from "./provider.registry.js";

export interface Resource {
  id: string; // The fully qualified ID, e.g. "render/render-primary"
  accountId: string;
  provider: ProviderName;
  name: string;
  role: string;
  url?: string;
  capabilities: Capability[];
  status: "unknown" | "healthy" | "degraded" | "down";
}

/**
 * Discovers and builds the active resource list based on available accounts.
 */
export async function listResources(): Promise<Resource[]> {
  const accounts = buildAccountRegistry();
  const resources: Resource[] = [];

  for (const account of accounts) {
    if (!account.available) continue;

    // For now, each account maps to a single macro-resource.
    // In Phase 3, the specific Provider Adapters will query the APIs 
    // to discover multiple micro-resources (e.g. 5 tables in Supabase).
    resources.push({
      id: `${account.provider}/${account.id}`,
      accountId: account.id,
      provider: account.provider,
      name: account.displayName,
      role: account.role,
      url: account.url,
      capabilities: account.capabilities,
      status: "unknown", // To be populated by Phase 4 Health Engine
    });
  }

  return resources;
}

export async function getResourceStatus(resourceId: string): Promise<string> {
  // Mock for now. Will be populated by Health Engine in Phase 4.
  return "Status check requires Phase 3 Provider Adapters.";
}
