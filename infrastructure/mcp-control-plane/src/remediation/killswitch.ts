import { buildAccountRegistry } from "../registry/account.registry.js";

export class KillSwitchManager {
  private autonomyEnabled: boolean = true;

  public isAutonomyEnabled(): boolean {
    return this.autonomyEnabled;
  }

  /**
   * Returns true only when core dependencies (Render, Supabase, Redis) are configured/available.
   * Prevents blind L2 autonomous remediation when dependency visibility is degraded.
   */
  public areCoreDependenciesVerified(): boolean {
    const accounts = buildAccountRegistry();
    const coreIds = ["render-primary", "supabase-primary", "redis-primary"];
    return coreIds.every((id) => accounts.find((a) => a.id === id)?.available === true);
  }

  public getEffectiveMode(): string {
    if (!this.autonomyEnabled) {
      return "L0 (Emergency Stop / Read-Only)";
    }
    if (!this.areCoreDependenciesVerified()) {
      return "L1 (Guarded / Approval-Required — Core Dependency Unverified)";
    }
    return "L2 (Autonomous)";
  }

  public emergencyStop(): void {
    if (!this.autonomyEnabled) return;
    
    this.autonomyEnabled = false;
    console.error(`[KILL SWITCH] 🚨 AUTONOMY DISABLED. Dropping to L0 (Read-Only) Mode.`);
    
    // Stop the background task scheduler if it's running
    import("../tasks/engine.js").then(({ globalTaskEngine }) => {
       globalTaskEngine.stopBackgroundScheduler();
       // Note: We don't forcefully kill running tasks right now, 
       // but we could mark them as failed or cancel them if we had cancellation tokens.
       console.error(`[KILL SWITCH] Background task scheduler stopped.`);
    }).catch(console.error);
  }

  public enableAutonomy(): void {
    if (this.autonomyEnabled) return;

    this.autonomyEnabled = true;
    console.log(`[KILL SWITCH] ✅ AUTONOMY RE-ENABLED.`);
  }
}

export const globalKillSwitch = new KillSwitchManager();
