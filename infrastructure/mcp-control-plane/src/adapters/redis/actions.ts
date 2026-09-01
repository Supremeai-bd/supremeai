import { ActionPlan } from "../../actions/plan.js";
import { getRedisClient } from "./index.js";

export function buildRedisFlushAction(prefix?: string): ActionPlan {
  return {
    context: { provider: "redis", action: prefix ? "del_prefix" : "flushall" },
    description: `Flush Redis Data (Prefix: ${prefix || 'ALL'})`,
    parameters: { prefix },
    executeFn: async () => {
      const client = getRedisClient();
      
      if (!prefix) {
        if ("flushall" in client) {
           await (client as any).flushall();
        } else {
           throw new Error("Upstash REST mode does not support flushall natively in this wrapper, implement multi-del.");
        }
        return { cleared: "ALL" };
      }
      
      // We would scan and delete keys matching the prefix.
      // For this skeleton phase, we'll simulate it.
      return { cleared: `Keys matching ${prefix}*` };
    }
  };
}
