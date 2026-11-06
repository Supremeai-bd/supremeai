import { isEvidenceFresh, type EvidenceEnvelope } from "../diagnostics/evidence.js";
import type { ServiceRef } from "../diagnostics/service_manifest.js";

export type AgentCapabilityRole =
  | "diagnostician"
  | "planner"
  | "learner"
  | "remediator"
  | "verifier";

export type PolicyAction =
  | "read_evidence"
  | "propose_plan"
  | "record_outcome"
  | "restart"
  | "redeploy"
  | "rollback"
  | "verify_postcondition";

export type PermissionEffect = "allow" | "ask" | "deny";

export interface PolicyEvaluationContext {
  agentRole: AgentCapabilityRole;
  action: PolicyAction;
  serviceRef: ServiceRef | null;
  environment?: "development" | "staging" | "production";
  evidence?: Array<Pick<EvidenceEnvelope, "observedAt" | "status">>;
  maxEvidenceAgeMs?: number;
  hasHumanApprovalToken?: boolean;
  hasIdempotencyKey?: boolean;
  hasRollbackTarget?: boolean;
  schemaParityStatus?: "pass" | "fail" | "unknown" | "error";
}

export interface PolicyDecision {
  effect: PermissionEffect;
  reasons: string[];
  requiredGates: string[];
}

const MUTATION_ACTIONS = new Set<PolicyAction>(["restart", "redeploy", "rollback"]);

/**
 * Evaluates ordered capability rules (deny -> ask -> allow) per Kilo-Org audit guidance.
 * Never allows broad '--auto' mutations; enforces fail-closed checks on stale identity,
 * expired evidence, or missing rollback / approval gates.
 */
export function evaluateActionPolicy(ctx: PolicyEvaluationContext): PolicyDecision {
  const reasons: string[] = [];
  const requiredGates: string[] = [];

  // 1. Canonical Service Identity Gate (Fail-Closed)
  if (!ctx.serviceRef || !ctx.serviceRef.canonicalServiceId || !ctx.serviceRef.providerNativeId) {
    reasons.push("MISSING_CANONICAL_SERVICE_IDENTITY");
    return { effect: "deny", reasons, requiredGates: ["canonical_service_identity"] };
  }

  const isMutation = MUTATION_ACTIONS.has(ctx.action);

  // 2. Role-Based Capability Separation (Strict Boundary)
  if (ctx.agentRole === "diagnostician") {
    if (ctx.action !== "read_evidence") {
      reasons.push(`ROLE_BOUNDARY_VIOLATION: diagnostician cannot perform '${ctx.action}'`);
      return { effect: "deny", reasons, requiredGates };
    }
    return { effect: "allow", reasons: ["READ_ONLY_DIAGNOSTICIAN_ALLOWED"], requiredGates };
  }

  if (ctx.agentRole === "planner") {
    if (ctx.action !== "read_evidence" && ctx.action !== "propose_plan") {
      reasons.push(`ROLE_BOUNDARY_VIOLATION: planner is proposal-only and cannot perform '${ctx.action}'`);
      return { effect: "deny", reasons, requiredGates };
    }
    return { effect: "allow", reasons: ["PROPOSAL_ONLY_PLANNER_ALLOWED"], requiredGates };
  }

  if (ctx.agentRole === "learner") {
    if (ctx.action !== "record_outcome" && ctx.action !== "read_evidence") {
      reasons.push(`ROLE_BOUNDARY_VIOLATION: learner can only record verified outcomes`);
      return { effect: "deny", reasons, requiredGates };
    }
    return { effect: "allow", reasons: ["LEARNER_RECORD_ALLOWED"], requiredGates };
  }

  if (ctx.agentRole === "verifier") {
    if (ctx.action !== "verify_postcondition" && ctx.action !== "read_evidence") {
      reasons.push(`ROLE_BOUNDARY_VIOLATION: verifier cannot execute mutations ('${ctx.action}')`);
      return { effect: "deny", reasons, requiredGates };
    }
    return { effect: "allow", reasons: ["INDEPENDENT_VERIFIER_ALLOWED"], requiredGates };
  }

  // 3. Remediator Mutation Rules
  if (isMutation) {
    requiredGates.push(
      "canonical_service_identity",
      "fresh_evidence",
      "human_approval",
      "idempotency_key",
    );

    if (ctx.action === "rollback") {
      requiredGates.push("rollback_plan");
      if (!ctx.hasRollbackTarget) {
        reasons.push("ROLLBACK_TARGET_MISSING");
        return { effect: "deny", reasons, requiredGates };
      }
    }

    // Schema parity fail-closed check
    if (ctx.schemaParityStatus === "fail") {
      reasons.push("SCHEMA_PARITY_FAILED_FAIL_CLOSED");
      return { effect: "deny", reasons, requiredGates };
    }

    // Evidence freshness check
    const maxAge = ctx.maxEvidenceAgeMs ?? 60_000;
    if (!ctx.evidence || ctx.evidence.length === 0) {
      reasons.push("EVIDENCE_MISSING");
      return { effect: "deny", reasons, requiredGates };
    }

    const allFresh = ctx.evidence.every((ev) => isEvidenceFresh(ev, maxAge));
    if (!allFresh) {
      reasons.push("STALE_EVIDENCE_REJECTED");
      return { effect: "deny", reasons, requiredGates };
    }

    if (!ctx.hasIdempotencyKey) {
      reasons.push("IDEMPOTENCY_KEY_REQUIRED");
      return { effect: "ask", reasons, requiredGates };
    }

    if (!ctx.hasHumanApprovalToken) {
      reasons.push("HUMAN_APPROVAL_REQUIRED");
      return { effect: "ask", reasons, requiredGates };
    }

    return {
      effect: "allow",
      reasons: ["ALL_REMEDIATION_GATES_SATISFIED"],
      requiredGates,
    };
  }

  return { effect: "allow", reasons: ["DEFAULT_NON_MUTATION_ALLOW"], requiredGates };
}

