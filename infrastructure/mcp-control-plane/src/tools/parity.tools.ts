import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

interface ParityCheck {
  component: string;
  status: "configuration_present" | "parity_verified" | "drift_detected" | "verification_failed" | "unconfigured";
  details: Record<string, unknown>;
}

async function runParityAudit(): Promise<{ status: string; checks: ParityCheck[] }> {
  const checks: ParityCheck[] = [];

  const envValue = (key: string): string | undefined => process.env[key];

  checks.push({
    component: "render",
    status: envValue("RENDER_API_KEY") ? "configuration_present" : "unconfigured",
    details: { note: "Render node SHA comparison requires RENDER_API_KEY" },
  });

  checks.push({
    component: "cloudflare",
    status: envValue("CLOUDFLARE_API_TOKEN") ? "configuration_present" : "unconfigured",
    details: { note: "Cloudflare deployment version inspection requires CLOUDFLARE_API_TOKEN" },
  });

  checks.push({
    component: "supabase",
    status: envValue("SUPABASE_URL") ? "configuration_present" : "unconfigured",
    details: { note: "Schema migration parity requires SUPABASE_URL" },
  });

  checks.push({
    component: "redis",
    status: envValue("REDIS_URL") ? "configuration_present" : "unconfigured",
    details: { note: "Queue backlog inspection requires REDIS_URL" },
  });

  checks.push({
    component: "infisical",
    status: envValue("INFISICAL_TOKEN") ? "configuration_present" : "unconfigured",
    details: { note: "Secret completeness cross-reference requires INFISICAL_TOKEN" },
  });

  checks.push({
    component: "github_repositories",
    status: envValue("GITHUB_TOKEN") ? "configuration_present" : "unconfigured",
    details: {
      topology: "Pure 2-Repository Topology",
      activeRepositories: [
        "Supremeai-bd/supremeai",
        "Supremeai-bd/supremeai-studio",
      ],
      retiredSatellites: [
        "supremeai-core",
        "supremeai-api",
        "supremeai-browser",
        "supremeai-vscode",
      ],
      note: "Commit and PR parity tracked across the 2 active repositories. Historical satellites are archived and read-only.",
    },
  });

  const hasDrift = checks.some((c) => c.status === "drift_detected" || c.status === "verification_failed");
  // `configuration_present` indicates credentials exist, but live commit/schema/secret
  // comparisons have not yet been evaluated end-to-end.
  const hasUnverifiedChecks = checks.some((c) => c.status === "configuration_present" || c.status === "unconfigured");
  return {
    status: hasDrift ? "drift_detected" : hasUnverifiedChecks ? "unverified" : "parity_verified",
    checks,
  };
}

export async function registerParityTools(server: McpServer): Promise<void> {
  const handler = async () => {
    const result = await runParityAudit();
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  };

  // Single registration ONLY. The MCP SDK normalizes tool names to [a-z0-9_-],
  // so "system.parity_audit" collides with "system_parity_audit" and the second
  // server.tool() call throws "already registered" at startup - which crashed the
  // whole registerAllTools chain and left Render deploys update_failed (WO #2211,
  // live 2026-10-28: build succeeds, container boot crashes, Render rolls back).
  server.tool("system_parity_audit", "Run a multi-platform commit/schema/secret parity audit", {}, { readOnlyHint: true, idempotentHint: true }, handler as any);
}

export { runParityAudit };
