import { globalHealthCache, HealthSnapshot } from "./snapshot.js";
import { globalIncidentEngine, IncidentAlert } from "./incident.js";

// Import all adapter checks
import { getServiceHealth } from "../adapters/render/index.js";
import { getHealth as getSupabaseHealth } from "../adapters/supabase/index.js";
import { pingRedis } from "../adapters/redis/index.js";
import { getWorkerStatus } from "../adapters/cloudflare/index.js";
import { auditSecrets } from "../adapters/infisical/index.js";
import { getAuthStatus } from "../adapters/firebase/index.js";
import { checkStripe, checkVercel, checkFirecrawl, checkKaggle, checkQdrant } from "../adapters/misc/index.js";
import { testProvider, listProviders } from "../adapters/ai/index.js";
import { checkTelegram, checkDiscord } from "../adapters/notify/index.js";

export interface SweepReport {
  timestamp: string;
  durationMs: number;
  incidents: IncidentAlert[];
  snapshots: Record<string, HealthSnapshot>;
}

export class HealthEngine {
  private maxConsecutiveFailuresBeforeCircuitOpen = 3;

  /**
   * Executes a single health check with circuit breaker logic.
   */
  private async executeCheck(
    provider: string,
    checkFn: () => Promise<any>
  ): Promise<HealthSnapshot> {
    const oldSnap = globalHealthCache.getSnapshot(provider);
    
    // Check Circuit Breaker
    if (oldSnap && oldSnap.status === "circuit_open") {
      // Very simple circuit breaker: stays open until manually reset or TTL expires (handled elsewhere)
      // For now, we will attempt a half-open probe.
      console.log(`[HealthEngine] Circuit breaker half-open for ${provider}. Attempting probe...`);
    }

    try {
      const data = await checkFn();
      
      const newSnap: HealthSnapshot = {
        provider,
        status: "healthy",
        lastCheckMs: Date.now(),
        consecutiveFailures: 0,
        data
      };
      
      return newSnap;
    } catch (err: any) {
      const consecutiveFailures = (oldSnap?.consecutiveFailures || 0) + 1;
      const status = consecutiveFailures >= this.maxConsecutiveFailuresBeforeCircuitOpen ? "circuit_open" : "down";
      
      const newSnap: HealthSnapshot = {
        provider,
        status,
        lastCheckMs: Date.now(),
        consecutiveFailures,
        error: err.message || "Unknown error"
      };
      
      return newSnap;
    }
  }

  /**
   * Runs a full parallel sweep of all configured providers.
   * Caches results and generates incidents.
   */
  public async runFullSweep(): Promise<SweepReport> {
    const start = Date.now();
    const incidents: IncidentAlert[] = [];
    
    // Define all providers and their check functions
    const checks: Record<string, () => Promise<any>> = {
      "render": () => getServiceHealth("render-primary", "srv-dabiaknqj5pc73a47mvg"),
      "supabase": () => getSupabaseHealth("supabase-primary"),
      "redis": () => pingRedis(),
      "cloudflare": () => getWorkerStatus(),
      "infisical": () => auditSecrets(),
      "firebase": () => getAuthStatus(),
      "stripe": () => checkStripe(),
      "vercel": () => checkVercel(),
      "firecrawl": () => checkFirecrawl(),
      "kaggle": () => checkKaggle(),
      "qdrant": () => checkQdrant(),
      "telegram": () => checkTelegram(),
      "discord": () => checkDiscord(),
    };

    // Dynamically add AI providers
    try {
      const aiProviders = listProviders() as any[];
      for (const p of aiProviders) {
        checks[`ai-${p.provider}`] = () => testProvider(p.provider);
      }
    } catch(e) {
      // Ignore if AI providers fail to list
    }

    // Execute all checks in parallel
    const promises = Object.entries(checks).map(async ([provider, fn]) => {
      const oldSnap = globalHealthCache.getSnapshot(provider);
      const newSnap = await this.executeCheck(provider, fn);
      
      // Update Cache
      globalHealthCache.setSnapshot(newSnap);
      
      // Evaluate Incidents
      const incident = globalIncidentEngine.evaluateTransition(
        provider,
        oldSnap,
        newSnap.status,
        newSnap.error
      );
      
      if (incident) {
        incidents.push(incident);
        console.warn(`[HealthEngine] Incident Detected: [${incident.type}] ${incident.message}`);
      }
    });

    await Promise.allSettled(promises);

    return {
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - start,
      incidents,
      snapshots: globalHealthCache.getAllSnapshots()
    };
  }
}

export const globalHealthEngine = new HealthEngine();
