import type { UserRole } from "./auth.context.js";

export type McpAccessMode = "public_viewer" | "viewer" | "agent" | "admin";
export type McpCapabilityClass = "safe" | "confirmation" | "restricted";

export interface McpAccessContext {
  mode: McpAccessMode;
  role: UserRole;
  authenticated: boolean;
  tenantBound: boolean;
  clientId?: string;
  scopes: string[];
}

export interface McpCapabilityMetadata {
  name: string;
  kind: "tool" | "resource" | "prompt";
  access: McpCapabilityClass;
  requiredScope?: string;
  riskLevel: "R0" | "R1" | "R2" | "R3" | "R4" | "R5" | "R6";
  dataClassification: "public" | "internal" | "tenant_private" | "secret";
  approvalRequired: boolean;
}

export const publicSafeCapabilities: readonly McpCapabilityMetadata[] = [
  { name: "control-tower://server/manifest", kind: "resource", access: "safe", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
  { name: "control-tower://system/health", kind: "resource", access: "safe", requiredScope: "health:read", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
  { name: "system.health", kind: "tool", access: "safe", requiredScope: "health:read", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
  { name: "system.summary", kind: "tool", access: "safe", requiredScope: "system:read", riskLevel: "R0", dataClassification: "public", approvalRequired: false },
];

export function canAccessCapability(context: McpAccessContext, capability: McpCapabilityMetadata): boolean {
  if (context.mode === "public_viewer") {
    return capability.access === "safe" && capability.dataClassification === "public";
  }
  if (capability.dataClassification === "secret") return context.mode === "admin";
  if (capability.access === "restricted") return context.mode === "admin" || context.mode === "agent";
  if (capability.requiredScope && !context.scopes.includes("*") && !context.scopes.includes(capability.requiredScope)) return false;
  return true;
}

export function accessModeFor(role: UserRole | null, authenticated: boolean): McpAccessMode {
  if (!authenticated || role === null) return "public_viewer";
  return role;
}

export function publicAccessManifest() {
  return {
    mode: "public_viewer" as const,
    connection: "instant",
    authentication: "only required for protected capabilities",
    capabilities: publicSafeCapabilities,
    semantics: { safe: "read-only and public", confirmation: "requires approval", restricted: "requires authenticated scope" },
  };
}

export function isPublicSafeResource(uri: string): boolean {
  return publicSafeCapabilities.some((capability) => capability.kind === "resource" && capability.name === uri);
}
