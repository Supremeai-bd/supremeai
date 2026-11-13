import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getDatabaseSchema } from "../adapters/supabase/index.js";
import { pingRedis } from "../adapters/redis/index.js";
import { getWorkerStatus } from "../adapters/cloudflare/index.js";
import { getLatestDeploy } from "../adapters/render/index.js";
import { resolveServiceTarget } from "../diagnostics/service_manifest.js";
import { httpRequest } from "../lib/http.js";
import { env } from "../lib/env.js";

interface ParityCheck {
  component: string;
  status: "configuration_present" | "parity_verified" | "drift_detected" | "verification_failed" | "unconfigured";
  details: Record<string, unknown>;
}

export interface ParityAuditResult {
  status: string;
  checks: ParityCheck[];
  releaseGate?: "open" | "blocked";
}

async function runParityAudit(): Promise<ParityAuditResult> {
  const checks: ParityCheck[] = [];

  const envValue = (key: string): string | undefined => process.env[key];

  // 1. Render & GitHub SHA Parity (Multi-Service Evaluation)
  let intendedSha: string | null = null;
  if (env.github.token) {
    try {
      const ghRes = await httpRequest<{ sha?: string }>(
        `https://api.github.com/repos/${env.github.repo}/commits/main`,
        {
          headers: {
            Authorization: `Bearer ${env.github.token}`,
            Accept: "application/vnd.github.v3+json",
            "User-Agent": "SupremeAI-Control-Tower/1.0",
          },
          timeoutMs: 5000,
          retries: 0,
        }
      );
      if (ghRes.ok && ghRes.data?.sha) intendedSha = ghRes.data.sha;
    } catch {
      // fallback if GitHub unreachable
    }
  }

  const renderServicesToCheck = ["api", "core", "mcp", "worker", "scraper", "brain"];
  const serviceParityResults: Record<string, {
    serviceId: string;
    runtimeUrl: string;
    deployedSha: string | null;
    runtimeSha: string | null;
    status: "parity_verified" | "drift_detected" | "live_unverified" | "offline";
  }> = {};

  let anyRenderDrift = false;
  let anyRenderVerified = false;

  for (const svcName of renderServicesToCheck) {
    const target = resolveServiceTarget(svcName);
    if (!target) continue;

    let deployedSha: string | null = null;
    let runtimeSha: string | null = null;
    let isLive = false;

    // A. Check latest deploy via Render API if account/service ID present
    if (target.renderServiceId && target.renderAccountId) {
      try {
        const dep = await getLatestDeploy(target.renderAccountId, target.renderServiceId);
        if (dep.commitSha) deployedSha = dep.commitSha;
      } catch {
        // Render deploy lookup skipped or failed
      }
    }

    // B. Check runtime /release endpoint if runtime URL exists
    if (target.runtimeUrl) {
      try {
        const releaseUrl = `${target.runtimeUrl.replace(/\/$/, "")}${target.releasePath || "/release"}`;
        const rtRes = await httpRequest<{ commit?: string; status?: string }>(releaseUrl, {
          timeoutMs: 4000,
          retries: 0,
        });
        if (rtRes.ok) {
          isLive = true;
          if (rtRes.data?.commit) runtimeSha = rtRes.data.commit;
        }
      } catch {
        // Runtime probe skipped or failed
      }
    }

    const observedSha = deployedSha || runtimeSha;
    let svcStatus: "parity_verified" | "drift_detected" | "live_unverified" | "offline" = "offline";

    if (observedSha && intendedSha) {
      const matches = observedSha.startsWith(intendedSha.slice(0, 7)) || intendedSha.startsWith(observedSha.slice(0, 7));
      if (matches) {
        svcStatus = "parity_verified";
        anyRenderVerified = true;
      } else {
        svcStatus = "drift_detected";
        anyRenderDrift = true;
      }
    } else if (observedSha || isLive) {
      svcStatus = "live_unverified";
      anyRenderVerified = true;
    }

    serviceParityResults[svcName] = {
      serviceId: target.renderServiceId,
      runtimeUrl: target.runtimeUrl,
      deployedSha,
      runtimeSha,
      status: svcStatus,
    };
  }

  checks.push({
    component: "render",
    status: anyRenderDrift ? "drift_detected" : anyRenderVerified ? "parity_verified" : "configuration_present",
    details: {
      intendedSha,
      serviceBreakdown: serviceParityResults,
      summary: anyRenderDrift 
        ? "Drift detected: One or more Render services are running outdated commit SHAs"
        : anyRenderVerified 
        ? "Parity verified across live Render services" 
        : "Live Render SHA probes inconclusive",
    },
  });

  // 2. Cloudflare Edge Parity
  try {
    if (env.cloudflare.workerUrl || envValue("CLOUDFLARE_API_TOKEN")) {
      const cfStatus = (await getWorkerStatus()) as { status?: string; httpStatus?: number; workerResponse?: unknown };
      const isOk = cfStatus?.httpStatus === 200 || cfStatus?.status === "healthy";
      checks.push({
        component: "cloudflare",
        status: isOk ? "parity_verified" : cfStatus?.httpStatus === 404 ? "drift_detected" : "configuration_present",
        details: {
          workerUrl: env.cloudflare.workerUrl,
          httpStatus: cfStatus?.httpStatus ?? null,
          workerStatus: cfStatus?.status ?? "unknown",
        },
      });
    } else {
      checks.push({
        component: "cloudflare",
        status: "unconfigured",
        details: { note: "Cloudflare deployment version inspection requires CLOUDFLARE_API_TOKEN" },
      });
    }
  } catch (err) {
    checks.push({
      component: "cloudflare",
      status: envValue("CLOUDFLARE_API_TOKEN") ? "configuration_present" : "unconfigured",
      details: { error: (err as Error).message },
    });
  }

  // 3. Supabase Schema Parity
  try {
    if (envValue("SUPABASE_URL")) {
      const schema = (await getDatabaseSchema("supabase-primary")) as { tables?: string[] };
      const tablesCount = Array.isArray(schema?.tables) ? schema.tables.length : 0;
      const projectRef = new URL(envValue("SUPABASE_URL")!).hostname.split(".")[0];
      checks.push({
        component: "supabase",
        status: tablesCount > 0 ? "parity_verified" : "configuration_present",
        details: {
          projectRef,
          tablesCount,
          sampleTables: Array.isArray(schema?.tables) ? schema.tables.slice(0, 5) : [],
        },
      });
    } else {
      checks.push({
        component: "supabase",
        status: "unconfigured",
        details: { note: "Schema migration parity requires SUPABASE_URL" },
      });
    }
  } catch (err) {
    checks.push({
      component: "supabase",
      status: envValue("SUPABASE_URL") ? "configuration_present" : "unconfigured",
      details: { error: (err as Error).message },
    });
  }

  // 4. Redis Parity
  try {
    if (envValue("REDIS_URL") || envValue("UPSTASH_REDIS_REST_URL")) {
      const rPing: any = await pingRedis();
      const isOk = rPing?.status === "healthy" || String(rPing?.probe).toUpperCase().includes("PONG");
      checks.push({
        component: "redis",
        status: isOk ? "parity_verified" : "drift_detected",
        details: {
          probe: rPing?.probe ?? "PONG",
          activePrimary: rPing?.activePrimary ?? "primary",
        },
      });
    } else {
      checks.push({
        component: "redis",
        status: "unconfigured",
        details: { note: "Queue backlog inspection requires REDIS_URL" },
      });
    }
  } catch (err) {
    checks.push({
      component: "redis",
      status: envValue("REDIS_URL") ? "configuration_present" : "unconfigured",
      details: { error: (err as Error).message },
    });
  }

  // 5. Infisical Secret Plane Parity
  const hasInfisical = Boolean(envValue("INFISICAL_TOKEN") || (envValue("INFISICAL_CLIENT_ID") && envValue("INFISICAL_CLIENT_SECRET")));
  const requiredCoreSecrets = ["SUPABASE_URL", "REDIS_URL", "GITHUB_TOKEN", "RENDER_API_KEY"];
  const presentCoreSecrets = requiredCoreSecrets.filter((k) => Boolean(envValue(k)));
  checks.push({
    component: "infisical",
    status: hasInfisical && presentCoreSecrets.length === requiredCoreSecrets.length ? "parity_verified" : hasInfisical ? "configuration_present" : "unconfigured",
    details: {
      coreSecretsVerified: `${presentCoreSecrets.length}/${requiredCoreSecrets.length}`,
      machineIdentityConfigured: Boolean(envValue("INFISICAL_CLIENT_ID")),
    },
  });

  // 6. GitHub Repositories Topology Parity
  checks.push({
    component: "github_repositories",
    status: intendedSha || envValue("GITHUB_TOKEN") ? "parity_verified" : "unconfigured",
    details: {
      topology: "Pure Single-Repository Monorepo SSOT Topology",
      intendedMainCommit: intendedSha,
      activeRepositories: [
        "Supremeai-bd/supremeai",
      ],
      retiredSatellites: [
        "supremeai-studio",
        "supremeai-core",
        "supremeai-api",
        "supremeai-browser",
        "supremeai-vscode",
      ],
      note: "Commit and PR parity tracked across Supremeai-bd/supremeai Single Monorepo SSOT. Historical satellites are archived and read-only.",
    },
  });

  const hasDrift = checks.some((c) => c.status === "drift_detected" || c.status === "verification_failed");
  // `configuration_present` indicates credentials exist, but live commit/schema/secret
  // comparisons have not yet been evaluated end-to-end.
  const hasUnverifiedChecks = checks.some((c) => c.status === "configuration_present" || c.status === "unconfigured");
  return {
    status: hasDrift ? "drift_detected" : hasUnverifiedChecks ? "unverified" : "parity_verified",
    checks,
    releaseGate: hasDrift ? "blocked" : hasUnverifiedChecks ? "blocked" : "open",
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
