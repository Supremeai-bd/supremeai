import { randomUUID } from "node:crypto";
import { type EvidenceCheck, type EvidenceStatus, fact } from "../diagnostics/evidence.js";

export type PlanStepStatus = "pending" | "in_progress" | "completed" | "failed" | "skipped" | "rolled_back";

export interface PlanStep {
  id: string;
  title: string;
  tool: string;
  params: Record<string, unknown>;
  dependsOn: string[];
  timeoutMs: number;
  retryPolicy: { maxRetries: number; backoffMs: number };
  idempotencyKey: string;
  rollbackAction?: {
    tool: string;
    params: Record<string, unknown>;
  };
  approvalRequired: boolean;
  expectedEvidence: {
    type: string;
    checkName: string;
    description: string;
  };
  status?: PlanStepStatus;
  executionResult?: unknown;
}

export interface DAGValidationResult {
  valid: boolean;
  cycles?: string[];
  executionWaves: string[][];
  totalSteps: number;
}

export interface ExecutionPlan {
  planId: string;
  goal: string;
  targetService?: string;
  intent: "remediation" | "deployment" | "migration" | "custom";
  status: "draft" | "approved" | "in_progress" | "completed" | "failed" | "rolled_back";
  createdAt: string;
  executionWaves: string[][];
  steps: PlanStep[];
}

/**
 * Validates that the plan steps form a Directed Acyclic Graph (DAG)
 * and computes topological execution waves for parallel step dispatch.
 */
export function validateDAG(steps: PlanStep[]): DAGValidationResult {
  const stepMap = new Map<string, PlanStep>();
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  for (const step of steps) {
    stepMap.set(step.id, step);
    inDegree.set(step.id, 0);
    adjacency.set(step.id, []);
  }

  // Build graph edges and calculate in-degrees
  for (const step of steps) {
    for (const depId of step.dependsOn) {
      if (!stepMap.has(depId)) {
        return {
          valid: false,
          cycles: [`Missing dependency step: '${depId}' required by '${step.id}'`],
          executionWaves: [],
          totalSteps: steps.length,
        };
      }
      adjacency.get(depId)!.push(step.id);
      inDegree.set(step.id, (inDegree.get(step.id) || 0) + 1);
    }
  }

  // Kahn's algorithm for topological sorting in waves
  const executionWaves: string[][] = [];
  let currentWave = steps.filter((s) => (inDegree.get(s.id) || 0) === 0).map((s) => s.id);

  let processedCount = 0;

  while (currentWave.length > 0) {
    executionWaves.push(currentWave);
    processedCount += currentWave.length;

    const nextWave: string[] = [];
    for (const nodeId of currentWave) {
      for (const neighbor of adjacency.get(nodeId) || []) {
        inDegree.set(neighbor, inDegree.get(neighbor)! - 1);
        if (inDegree.get(neighbor) === 0) {
          nextWave.push(neighbor);
        }
      }
    }
    currentWave = nextWave;
  }

  if (processedCount < steps.length) {
    return {
      valid: false,
      cycles: ["Circular dependency detected in plan steps"],
      executionWaves: [],
      totalSteps: steps.length,
    };
  }

  return {
    valid: true,
    executionWaves,
    totalSteps: steps.length,
  };
}

/**
 * Synthesizes a proven remediation DAG plan for a specific diagnostic failure layer.
 */
export function generateRemediationPlan(service: string, failureLayer: string): ExecutionPlan {
  const planId = `plan-${randomUUID().slice(0, 8)}`;
  let steps: PlanStep[] = [];

  if (failureLayer === "RELEASE_COMMIT_MISMATCH") {
    steps = [
      {
        id: "step-1-pre-check",
        title: `Verify git head and current release status for ${service}`,
        tool: "system.diagnose",
        params: { service, intent: "is_deploy_correct" },
        dependsOn: [],
        timeoutMs: 15_000,
        retryPolicy: { maxRetries: 2, backoffMs: 2_000 },
        idempotencyKey: `${planId}-step-1`,
        approvalRequired: false,
        expectedEvidence: {
          type: "diagnostic",
          checkName: "intended_source",
          description: "Intended git commit resolved",
        },
      },
      {
        id: "step-2-trigger-deploy",
        title: `Trigger Render deployment to align release with git commit for ${service}`,
        tool: "render_deploys_create",
        params: { service, clearCache: false },
        dependsOn: ["step-1-pre-check"],
        timeoutMs: 60_000,
        retryPolicy: { maxRetries: 1, backoffMs: 5_000 },
        idempotencyKey: `${planId}-step-2`,
        approvalRequired: true,
        rollbackAction: {
          tool: "render_deploys_rollback",
          params: { service },
        },
        expectedEvidence: {
          type: "deployment",
          checkName: "render_deploy_initiated",
          description: "Deploy job initiated on Render",
        },
      },
      {
        id: "step-3-post-verify",
        title: `Verify end-to-end release parity post-deploy for ${service}`,
        tool: "system.verify",
        params: { service, target: "release", expectedOutcome: "PROCEED_RELEASE_VERIFIED" },
        dependsOn: ["step-2-trigger-deploy"],
        timeoutMs: 30_000,
        retryPolicy: { maxRetries: 3, backoffMs: 10_000 },
        idempotencyKey: `${planId}-step-3`,
        approvalRequired: false,
        expectedEvidence: {
          type: "verification",
          checkName: "release_integrity",
          description: "Release commit matches deployed commit with HTTP 200 health",
        },
      },
    ];
  } else if (failureLayer === "SCHEMA_PARITY_BREACH") {
    steps = [
      {
        id: "step-1-inspect-schema",
        title: "Inspect current Supabase schema and detect missing tables",
        tool: "supabase.schema_inspect",
        params: { accountId: "supabase-primary" },
        dependsOn: [],
        timeoutMs: 15_000,
        retryPolicy: { maxRetries: 2, backoffMs: 2_000 },
        idempotencyKey: `${planId}-step-1`,
        approvalRequired: false,
        expectedEvidence: {
          type: "schema",
          checkName: "schema_inspect",
          description: "List of public database tables returned",
        },
      },
      {
        id: "step-2-verify-migrations",
        title: "Verify applied database migrations against repository migration files",
        tool: "system.verify",
        params: { service, target: "schema", expectedOutcome: "SCHEMA_PARITY_VERIFIED" },
        dependsOn: ["step-1-inspect-schema"],
        timeoutMs: 20_000,
        retryPolicy: { maxRetries: 2, backoffMs: 3_000 },
        idempotencyKey: `${planId}-step-2`,
        approvalRequired: false,
        expectedEvidence: {
          type: "verification",
          checkName: "schema_parity",
          description: "All core tables present in target schema",
        },
      },
    ];
  } else {
    // Default system degradation diagnosis & recovery plan
    steps = [
      {
        id: "step-1-deep-audit",
        title: `Execute deep health sweep across dependencies for ${service}`,
        tool: "system.diagnose",
        params: { service, intent: "root_cause" },
        dependsOn: [],
        timeoutMs: 15_000,
        retryPolicy: { maxRetries: 1, backoffMs: 2_000 },
        idempotencyKey: `${planId}-step-1`,
        approvalRequired: false,
        expectedEvidence: {
          type: "diagnostic",
          checkName: "root_cause",
          description: "Identifies failing layer and provides actionable findings",
        },
      },
      {
        id: "step-2-verify-health",
        title: `Verify restored health status for ${service}`,
        tool: "system.verify",
        params: { service, target: "service", expectedOutcome: "HEALTHY" },
        dependsOn: ["step-1-deep-audit"],
        timeoutMs: 20_000,
        retryPolicy: { maxRetries: 2, backoffMs: 5_000 },
        idempotencyKey: `${planId}-step-2`,
        approvalRequired: false,
        expectedEvidence: {
          type: "verification",
          checkName: "service_health",
          description: "Service endpoint returns HTTP 200 OK",
        },
      },
    ];
  }

  const dag = validateDAG(steps);

  return {
    planId,
    goal: `Remediate ${failureLayer} on service ${service}`,
    targetService: service,
    intent: "remediation",
    status: "draft",
    createdAt: new Date().toISOString(),
    executionWaves: dag.executionWaves,
    steps,
  };
}

/**
 * Creates and validates a custom execution plan.
 */
export function createCustomPlan(
  goal: string,
  targetService?: string,
  rawSteps?: Partial<PlanStep>[],
): ExecutionPlan {
  const planId = `plan-${randomUUID().slice(0, 8)}`;
  const steps: PlanStep[] = (rawSteps || []).map((s, idx) => ({
    id: s.id || `step-${idx + 1}`,
    title: s.title || `Execute step ${idx + 1}`,
    tool: s.tool || "system.diagnose",
    params: s.params || {},
    dependsOn: s.dependsOn || [],
    timeoutMs: s.timeoutMs || 15_000,
    retryPolicy: s.retryPolicy || { maxRetries: 1, backoffMs: 2_000 },
    idempotencyKey: s.idempotencyKey || `${planId}-step-${idx + 1}`,
    rollbackAction: s.rollbackAction,
    approvalRequired: s.approvalRequired ?? false,
    expectedEvidence: s.expectedEvidence || {
      type: "generic",
      checkName: "execution",
      description: "Step completes without unhandled errors",
    },
    status: "pending",
  }));

  const dag = validateDAG(steps);
  if (!dag.valid) {
    throw new Error(`Invalid Plan DAG: ${dag.cycles?.join("; ")}`);
  }

  return {
    planId,
    goal,
    targetService,
    intent: "custom",
    status: "draft",
    createdAt: new Date().toISOString(),
    executionWaves: dag.executionWaves,
    steps,
  };
}

