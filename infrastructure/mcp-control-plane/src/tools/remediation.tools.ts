import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { diagnoseRelease } from "./diagnostic.tools.js";
import { resolveServiceTarget } from "../diagnostics/service_manifest.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";

const idempotency = new Map<string, { expiresAt: number; result?: unknown }>();
const IDEMPOTENCY_TTL_MS = 15 * 60 * 1000;

function assertAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole) ? null : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

export async function registerRemediationTools(server: McpServer): Promise<void> {
  server.registerTool(
    "system.execute",
    {
      description: "Safe remediation planning gate (plan-only): precondition checks + approval token + idempotency + post-action verification. Does NOT execute live restart/redeploy until an adapter is wired; returns executed:false.",
      annotations: { readOnlyHint: false, idempotentHint: false, destructiveHint: true },
      inputSchema: {
        action: z.enum(["restart", "redeploy", "rollback"]).default("restart"),
        service: z.string().default("api"),
        approvalToken: z.string().optional().describe("Human-in-the-loop approval token. Required for any execution."),
        idempotencyKey: z.string().min(8).max(128).optional(),
        rollbackTargetCommit: z.string().optional().describe("Required for rollback action."),
      },
    },
    async ({ action, service, approvalToken, idempotencyKey, rollbackTargetCommit }) => {
      const denial = assertAccess("system.execute", "admin");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };

      const target = resolveServiceTarget(service);
      if (!target) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "rejected", reason: "SERVICE_NOT_MAPPED", service }) }] };
      }

      const caller = RequestContextStore.get();
      const key = `${caller?.tenantId ?? "default"}:${idempotencyKey ?? `${caller?.requestId ?? "request"}:${action}:${service}`}`;
      const now = Date.now();
      for (const [k, v] of idempotency) if (v.expiresAt <= now) idempotency.delete(k);
      const previous = idempotency.get(key);
      if (previous?.result) return { content: [{ type: "text", text: JSON.stringify(previous.result, null, 2) }] };
      if (previous) return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "rejected", reason: "REQUEST_IN_PROGRESS" }) }] };

      const pending: { expiresAt: number; result?: unknown } = { expiresAt: now + IDEMPOTENCY_TTL_MS };
      idempotency.set(key, pending);

      try {
        // Preconditions
        const preconditions: Record<string, boolean> = {};
        const diag = await diagnoseRelease(service, "is_deploy_correct");
        const truth = (diag as any).truthMatrix ?? {};
        preconditions.serviceMapped = Boolean(target);
        preconditions.dependenciesNotFailing = truth.dependencyHealth !== "fail";
        preconditions.noConfirmedCommitMismatch = truth.releaseIntegrity !== "fail";

        if (action === "rollback") {
          preconditions.rollbackTargetProvided = Boolean(rollbackTargetCommit && rollbackTargetCommit.trim());
          if (rollbackTargetCommit) {
            const intended = (diag as any).evidence?.latestWorkflowCommit ?? null;
            preconditions.rollbackTargetVerifiable = !intended || rollbackTargetCommit === intended || rollbackTargetCommit.length >= 7;
          }
        }

        const preconditionsPassed = Object.values(preconditions).every(Boolean);
        if (!preconditionsPassed) {
          const result = { status: "rejected", reason: "PRECONDITION_FAILED", action, service, preconditions };
          pending.result = result;
          return { isError: true, content: [{ type: "text", text: JSON.stringify(redactSensitiveData(result), null, 2) }] };
        }

        if (!approvalToken || approvalToken.trim().length < 8) {
          const result = { status: "rejected", reason: "APPROVAL_REQUIRED", action, service, preconditions, hint: "Supply a human approval token (>=8 chars) to proceed." };
          idempotency.delete(key);
          return { isError: true, content: [{ type: "text", text: JSON.stringify(redactSensitiveData(result), null, 2) }] };
        }

        // Execution is plan-only: no live restart/redeploy adapter is wired.
        // Record the intent and run post-action verification against current state.
        const result = {
          status: "planned",
          executed: false,
          executionAdapter: null,
          mode: "plan_only",
          executionMode: "plan_only",
          message: "Safe plan-only mode active: no destructive actions are applied without an approved live execution adapter.",
          action,
          service,
          note: "No live execution adapter is wired; remediation recorded and verified against current diagnostic state. Wire Render restart/redeploy adapter to enable live execution.",
          preconditions,
          approvalTokenFingerprint: (await import("../diagnostics/redaction.js")).fingerprintSecret(approvalToken),
          postVerification: {
            diagnosticStatus: (diag as any).status,
            truthMatrix: truth,
          },
          timestamp: new Date().toISOString(),
        };
        pending.result = result;
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(result), null, 2) }] };
      } catch (error) {
        idempotency.delete(key);
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "error", error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );
}
