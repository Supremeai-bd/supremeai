import { HealthSnapshot } from "./snapshot.js";
import { globalDependencyGraph } from "./dependency.js";

export interface IncidentAlert {
  id: string;
  provider: string;
  timestamp: string;
  type: "DEGRADED" | "OUTAGE" | "RECOVERY";
  message: string;
  impactedServices: string[];
}

export class IncidentEngine {
  /**
   * Evaluates the new snapshot against the old one to detect state transitions.
   * Emits an incident alert if a transition crosses a severity threshold.
   */
  public evaluateTransition(
    provider: string,
    oldSnap: HealthSnapshot | undefined,
    newStatus: HealthSnapshot["status"],
    errorDetails?: string
  ): IncidentAlert | null {
    const oldStatus = oldSnap?.status || "healthy";
    
    // No state change
    if (oldStatus === newStatus) {
      return null;
    }

    const impacted = globalDependencyGraph.getImpactedServices(provider);
    const timestamp = new Date().toISOString();
    const id = `INC-${Date.now().toString(36)}`;

    // Transition: Healthy -> Degraded/Down/Circuit Open
    if (oldStatus === "healthy" && newStatus !== "healthy") {
      const type = newStatus === "down" || newStatus === "circuit_open" ? "OUTAGE" : "DEGRADED";
      return {
        id,
        provider,
        timestamp,
        type,
        message: `Provider ${provider} transitioned to ${newStatus}. Error: ${errorDetails || "None"}`,
        impactedServices: impacted
      };
    }

    // Transition: Down/Degraded -> Healthy
    if (oldStatus !== "healthy" && newStatus === "healthy") {
      return {
        id,
        provider,
        timestamp,
        type: "RECOVERY",
        message: `Provider ${provider} has recovered and is now healthy.`,
        impactedServices: impacted
      };
    }

    // Degraded -> Down (Escalation)
    if (oldStatus === "degraded" && (newStatus === "down" || newStatus === "circuit_open")) {
       return {
        id,
        provider,
        timestamp,
        type: "OUTAGE",
        message: `Provider ${provider} escalated from degraded to ${newStatus}. Error: ${errorDetails || "None"}`,
        impactedServices: impacted
      };
    }

    return null;
  }
}

export const globalIncidentEngine = new IncidentEngine();
