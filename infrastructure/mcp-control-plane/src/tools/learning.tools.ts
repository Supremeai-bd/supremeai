import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { recordLearning, recallLearnings, learningStats, type MemoryTier, type MemoryStatus } from "../learning/learning_gate.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";

function assertAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole) ? null : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

export async function registerLearningTools(server: McpServer): Promise<void> {
  server.registerTool(
    "memory.learn",
    {
      description: "Record a learning into the 3-tier memory system (episodic/semantic/procedural) with a quality gate: candidate → trusted (only if verifiedBy supplied and no contradiction) → quarantined (on contradiction).",
      annotations: { readOnlyHint: false, idempotentHint: false },
      inputSchema: {
        tier: z.enum(["episodic", "semantic", "procedural"]),
        fact: z.string().min(1).max(4000),
        evidence: z.record(z.string(), z.unknown()).optional(),
        verifiedBy: z.string().optional().describe("Verifier identity (human or agent id). Required for trusted promotion."),
      },
    },
    async ({ tier, fact, evidence, verifiedBy }) => {
      const denial = assertAccess("memory.learn", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        const record = recordLearning({ tier: tier as MemoryTier, fact, evidence: evidence ?? {}, verifiedBy: verifiedBy ?? null });
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(record), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );

  server.registerTool(
    "memory.recall",
    {
      description: "Recall learnings from the 3-tier memory system. Filters by tier/status and ranks by token overlap with query. Trusted facts are preferred for procedural guidance.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        query: z.string().optional(),
        tier: z.enum(["episodic", "semantic", "procedural"]).optional(),
        status: z.enum(["candidate", "trusted", "quarantined"]).optional(),
        limit: z.number().int().min(1).max(100).default(20),
      },
    },
    async ({ query, tier, status, limit }) => {
      const denial = assertAccess("memory.recall", "viewer");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        const records = recallLearnings({ query, tier: (tier as MemoryTier) ?? null, status: (status as MemoryStatus) ?? null, limit });
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData({ count: records.length, records }), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );

  server.registerTool(
    "memory.learning_stats",
    {
      description: "Report counts of learnings by tier and status (candidate/trusted/quarantined).",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {},
    },
    async () => {
      const denial = assertAccess("memory.learning_stats", "viewer");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        return { content: [{ type: "text", text: JSON.stringify(learningStats(), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }) }] };
      }
    },
  );
}
