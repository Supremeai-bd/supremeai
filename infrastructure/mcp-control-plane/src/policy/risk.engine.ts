export type RiskLevel = "R0" | "R1" | "R2" | "R3" | "R4" | "R5" | "R6";

export interface ActionContext {
  provider: string; // e.g., 'render', 'supabase', 'system'
  action: string;   // e.g., 'summary', 'restart', 'deploy', 'delete_db'
}

export class RiskEngine {
  /**
   * Evaluates the risk level of a specific action.
   */
  public evaluate(context: ActionContext): RiskLevel {
    const { provider, action } = context;

    // R0: Safe Read-Only (System, Metrics, Health)
    if (provider === "system" || provider === "health" || action.includes("read") || action.includes("list") || action.includes("summary") || action.includes("status")) {
      return "R0";
    }

    // Define rules per provider
    if (provider === "render") {
      if (action === "restart" || action === "deploy") return "R2";
      if (action === "suspend") return "R4";
      if (action === "delete") return "R6";
    }

    if (provider === "supabase") {
      if (action === "restart") return "R3";
      if (action === "delete_table" || action === "drop_db") return "R6";
      if (action === "insert" || action === "update") return "R2"; // Data manipulation
    }

    if (provider === "redis") {
      if (action === "flushall") return "R5";
      if (action === "set") return "R1";
      if (action === "del") return "R2";
    }
    
    if (provider === "github") {
      if (action === "commit" || action === "push") return "R2";
      if (action === "delete_repo") return "R6";
    }

    // Default Fallback for Unknown Writes
    return "R3"; 
  }
}

export const globalRiskEngine = new RiskEngine();
