import type { UserRole } from "./auth.context.js";
import { RequestContextStore, roleRank } from "./auth.context.js";

// #110: mode union extended to mirror the 6-tier UserRole ladder.
// বাংলা মন্তব্য: মোড ইউনিয়ন ৬-স্তর রোল ল্যাডারের সাথে সমন্বিত।
export type McpAccessMode =
  | "public_viewer"
  | "viewer"
  | "restricted_viewer"
  | "repo_viewer"
  | "agent"
  | "admin"
  | "supremeadmin";
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
  // #110: tier-aware capability checks on the rank ladder (mode === role for
  // every authenticated caller — accessModeFor). secret ⇒ rank ≥ 4
  // (admin/supremeadmin); restricted ⇒ rank ≥ 3 (agent and above). The
  // read-only tiers (restricted_viewer=1, repo_viewer=2) therefore keep
  // access ONLY to safe/public capabilities gated by scopes — read-only stays
  // read-only. Legacy semantics preserved for the original 3 tiers.
  // বাংলা মন্তব্য: সিক্রেট ক্যাপাবিলিটি র‍্যাঙ্ক ≥ ৪, রিস্ট্রিক্টেড র‍্যাঙ্ক ≥ ৩ — রিড-অনলি স্তর শুধু সেফ ক্যাপাবিলিটি ব্যবহার করতে পারবে।
  // After the public_viewer early-return, mode is a real UserRole (mode ===
  // role for authenticated callers — accessModeFor), so rank lookup is direct.
  const rank = roleRank(context.mode as UserRole);
  if (capability.dataClassification === "secret") return rank >= 4;
  if (capability.access === "restricted") return rank >= 3;
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

/**
 * Central default-deny classification for every registered tool (#695).
 *
 * Works on the sanitized (wire) names — the `server.tool` override in index.ts
 * replaces dots with underscores before registration, so classification runs on
 * names like `action_render_deploy` / `system_health`.
 *
 * Classes:
 *  - access "safe" + dataClassification "public" → callable by every access
 *    mode, including anonymous public_viewer (advertised by
 *    publicAccessManifest()).
 *  - dataClassification "secret" → admin only (tools touching secrets/env-var
 *    values).
 *  - everything else defaults to "restricted" + "internal" → agent/admin only;
 *    anonymous public_viewer and viewer roles are denied. Unknown and dynamic
 *    (database-registered) tools fall into this class — deny by default.
 *
 * AUDIT-FIX (#1787): `agent_status` ও `agent_heartbeat` এখন "safe" + "public"
 * data classification পায় — কারণ #1767-এ no-auth guest clients auto-register
 * হওয়ার পর তাদের agent list দেখতে ও heartbeat পাঠাতে পারা উচিত। এই tools-এ
 * কোনো sensitive data নেই — agent_status শুধু slot name + derived state
 * দেখায়, agent_heartbeat শুধু slot validate করে ও Redis-এ heartbeat লেখে।
 */
export function classifyToolCapability(name: string): McpCapabilityMetadata {
  if (name === "system_summary" || name === "system_health") {
    return {
      name,
      kind: "tool",
      access: "safe",
      requiredScope: name === "system_health" ? "health:read" : "system:read",
      riskLevel: "R0",
      dataClassification: "public",
      approvalRequired: false,
    };
  }
  // AUDIT-FIX (#1787): agent_status ও agent_heartbeat public_viewer-ও call করতে পারবে।
  // এগুলো read-only (agent_status) অথবা slot-validated write (agent_heartbeat —
  // validateSlot শুধু "agent-N" format চেক করে, কোনো privilege escalation নেই)।
  if (name === "agent_status" || name === "agent_heartbeat") {
    return {
      name,
      kind: "tool",
      access: "safe",
      requiredScope: undefined,
      riskLevel: "R1",
      dataClassification: "public",
      approvalRequired: false,
    };
  }
  if (
    name.startsWith("infisical_") ||
    name === "github_list_secrets" ||
    name === "render_get_env_vars"
  ) {
    return {
      name,
      kind: "tool",
      access: "restricted",
      requiredScope: undefined,
      riskLevel: "R4",
      dataClassification: "secret",
      approvalRequired: false,
    };
  }
  return {
    name,
    kind: "tool",
    access: "restricted",
    requiredScope: undefined,
    riskLevel: "R2",
    dataClassification: "internal",
    approvalRequired: false,
  };
}

/**
 * Central default-deny gate for the tool-call path (#695).
 *
 * Returns `null` when the caller (from the same RequestContextStore the HTTP
 * routes populate) may execute the tool, or a human-readable denial message
 * when the role/capability check fails. No tool executes without passing this
 * check — the `server.tool` override in index.ts wraps EVERY handler with it.
 */
export function toolAccessError(toolName: string): string | null {
  const store = RequestContextStore.get();
  if (!store) {
    // Fail-closed: no request context at all (neither an HTTP transport nor the
    // trusted stdio path, which establishes an explicit admin context — see
    // auth.context.ts getRole() and index.ts startStdioServer, #698).
    return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  }
  const context: McpAccessContext = {
    mode: store.accessMode ?? accessModeFor(store.role, store.authenticated === true),
    role: store.role,
    authenticated: store.authenticated === true,
    tenantBound: store.tenantBound === true,
    clientId: store.clientId,
    scopes: store.scopes ?? [],
  };
  const capability = classifyToolCapability(toolName);
  if (canAccessCapability(context, capability)) return null;
  const requiredRole = capability.dataClassification === "secret" ? "admin" : "agent";
  return `Forbidden: tool '${toolName}' requires ${requiredRole} role or higher (default-deny RBAC). Present a valid MCP Bearer token with a sufficient role.`;
}
