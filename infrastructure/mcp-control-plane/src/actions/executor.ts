import { ActionPlan } from "./plan.js";
import { globalPolicyEngine } from "../policy/policy.engine.js";
import { globalApprovalManager } from "../policy/approvals/lifecycle.js";
import { globalHITLManager } from "../policy/approvals/hitl.js";
import { globalAuditLogger } from "../audit/audit.js";
import * as crypto from "node:crypto";

export interface ExecutionResult {
  status: "SUCCESS" | "FAILURE" | "PENDING_APPROVAL" | "DENIED";
  message: string;
  requestId?: string;
  correlationId?: string;
}

export class ActionExecutor {
  /**
   * Evaluates the action against the policy engine.
   * If ALLOWED, executes it.
   * If REQUIRE_APPROVAL, creates a HITL request.
   * If DENIED, rejects.
   * If an explicit overrideRequestId is provided and APPROVED, executes it.
   */
  public async execute(plan: ActionPlan, overrideRequestId?: string): Promise<ExecutionResult> {
    const correlationId = `ACT-${crypto.randomUUID().substring(0, 8)}`;
    
    // Check if there is an existing approved request
    if (overrideRequestId) {
      const req = globalApprovalManager.getRequest(overrideRequestId);
      if (!req) {
         return { status: "FAILURE", message: `Approval request ${overrideRequestId} not found or expired.` };
      }
      if (req.state !== "APPROVED") {
         return { status: "FAILURE", message: `Request ${overrideRequestId} is ${req.state}. Cannot execute.` };
      }
      
      // Execute directly
      return await this.performExecution(plan, correlationId);
    }

    // New Request -> Evaluate Policy
    const policyResult = globalPolicyEngine.evaluateAction(plan.context);

    if (policyResult.decision === "DENY") {
       return { status: "DENIED", message: policyResult.reason };
    }

    if (policyResult.decision === "REQUIRE_APPROVAL") {
       const req = globalApprovalManager.createRequest(plan.context, plan.parameters);
       await globalHITLManager.requestApproval(req, policyResult.riskLevel);
       return { 
         status: "PENDING_APPROVAL", 
         message: `Action requires approval (Risk: ${policyResult.riskLevel}). Request created.`,
         requestId: req.id 
       };
    }

    // Auto-Allowed (R0 / R1)
    return await this.performExecution(plan, correlationId);
  }

  private async performExecution(plan: ActionPlan, correlationId: string): Promise<ExecutionResult> {
    try {
      console.log(`[EXECUTOR] Starting ${plan.context.provider}.${plan.context.action}`);
      const result = await plan.executeFn();

      // Verification Step
      if (plan.verifyFn) {
        console.log(`[EXECUTOR] Verifying execution...`);
        const isHealthy = await plan.verifyFn();
        if (!isHealthy) {
          throw new Error("Post-execution verification failed.");
        }
      }

      globalAuditLogger.log({
        correlationId,
        provider: plan.context.provider,
        action: plan.context.action,
        status: "SUCCESS",
        details: { result, parameters: plan.parameters }
      });

      return { status: "SUCCESS", message: "Action executed successfully.", correlationId };
    } catch (err: any) {
      console.error(`[EXECUTOR] Execution failed: ${err.message}`);
      
      // Rollback Step
      if (plan.rollbackFn) {
        try {
          console.log(`[EXECUTOR] Attempting rollback...`);
          await plan.rollbackFn();
          console.log(`[EXECUTOR] Rollback succeeded.`);
        } catch (rollbackErr: any) {
          console.error(`[EXECUTOR] Rollback failed: ${rollbackErr.message}`);
        }
      }

      globalAuditLogger.log({
        correlationId,
        provider: plan.context.provider,
        action: plan.context.action,
        status: "FAILURE",
        details: { parameters: plan.parameters },
        error: err.message
      });

      return { status: "FAILURE", message: `Execution failed: ${err.message}`, correlationId };
    }
  }
}

export const globalActionExecutor = new ActionExecutor();
