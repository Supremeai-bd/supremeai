import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { generateRemediationPlan, createCustomPlan, validateDAG, type PlanStep } from "../planning/planner.js";
import { verifyOutcome } from "../planning/verifier.js";
import { savePlan, getPlan, listPlans, updatePlanStatus } from "../planning/plan_store.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";

function assertPlanningAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole)
    ? null
    : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

export async function registerPlanningTools(server: McpServer): Promise<void> {
  server.registerTool(
    "system.plan",
    {
      description: "DAG Execution Planner: Generates dependency-aware execution plans, computes topological execution waves, validates DAG acyclic invariants, and synthesizes remediation plans from diagnostic failure layers.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        action: z.enum(["generate_remediation", "create_custom", "validate_dag", "get_plan", "list_plans", "update_status"]).default("generate_remediation"),
        service: z.string().default("api"),
        failureLayer: z.string().optional().describe("Failure layer code, e.g. RELEASE_COMMIT_MISMATCH, SCHEMA_PARITY_BREACH, UPSTREAM_DEPENDENCY_FAILURE"),
        goal: z.string().optional().describe("High level goal for the plan"),
        steps: z.array(z.object({
          id: z.string(),
          title: z.string(),
          tool: z.string(),
          params: z.record(z.string(), z.unknown()).default({}),
          dependsOn: z.array(z.string()).default([]),
          timeoutMs: z.number().default(15000),
          approvalRequired: z.boolean().default(false),
        })).optional().describe("Custom plan steps (for create_custom or validate_dag)"),
        planId: z.string().optional().describe("Plan ID for get_plan / update_status"),
        status: z.enum(["draft", "approved", "in_progress", "completed", "failed", "rolled_back"]).optional().describe("New status for update_status"),
      },
    },
    async ({ action, service, failureLayer, goal, steps, planId, status }) => {
      const denial = assertPlanningAccess("system.plan", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };

      try {
        if (action === "generate_remediation") {
          const plan = generateRemediationPlan(service, failureLayer || "RELEASE_COMMIT_MISMATCH");
          savePlan(plan);
          return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(plan), null, 2) }] };
        }

        if (action === "validate_dag") {
          const formattedSteps: PlanStep[] = (steps || []).map((s) => ({
            ...s,
            retryPolicy: { maxRetries: 1, backoffMs: 2000 },
            idempotencyKey: `val-${s.id}`,
            expectedEvidence: { type: "generic", checkName: "execution", description: "validation check" },
          }));
          const dag = validateDAG(formattedSteps);
          return { content: [{ type: "text", text: JSON.stringify(dag, null, 2) }] };
        }

        if (action === "create_custom") {
          const plan = createCustomPlan(goal || `Custom plan for ${service}`, service, steps as any);
          savePlan(plan);
          return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(plan), null, 2) }] };
        }

        if (action === "get_plan") {
          if (!planId) return { isError: true, content: [{ type: "text", text: "planId required" }] };
          const plan = getPlan(planId);
          if (!plan) return { isError: true, content: [{ type: "text", text: `Plan not found: ${planId}` }] };
          return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(plan), null, 2) }] };
        }

        if (action === "list_plans") {
          const plans = listPlans(20);
          return { content: [{ type: "text", text: JSON.stringify({ count: plans.length, plans: plans.map((p) => ({ planId: p.planId, goal: p.goal, status: p.status, createdAt: p.createdAt })) }, null, 2) }] };
        }

        if (action === "update_status") {
          if (!planId || !status) return { isError: true, content: [{ type: "text", text: "planId and status required" }] };
          const plan = updatePlanStatus(planId, status as any);
          if (!plan) return { isError: true, content: [{ type: "text", text: `Plan not found: ${planId}` }] };
          return { content: [{ type: "text", text: JSON.stringify({ planId: plan.planId, status: plan.status }, null, 2) }] };
        }

        return { isError: true, content: [{ type: "text", text: `Unknown action: ${action}` }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );

  server.registerTool(
    "system.verify",
    {
      description: "Post-Action Verification Gate: Validates execution results and service states against empirical evidence contracts. Fail-closed: unverified evidence never produces a verified outcome.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        target: z.enum(["release", "schema", "service", "generic"]).default("release"),
        service: z.string().default("api"),
        expectedOutcome: z.string().default("healthy"),
        facts: z.array(z.object({
          name: z.string(),
          status: z.enum(["pass", "fail", "unknown", "error"]),
          value: z.unknown().optional(),
        })).optional(),
      },
    },
    async ({ target, service, expectedOutcome, facts }) => {
      const denial = assertPlanningAccess("system.verify", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };

      try {
        const report = await verifyOutcome(target, service, expectedOutcome, facts as any);
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(report), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );
}
