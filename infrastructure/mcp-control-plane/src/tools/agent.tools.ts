import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { RequestContextStore } from "../policy/auth.context.js";
import {
  listHeartbeats,
  recordHeartbeat,
  validateSlot,
} from "../registry/agent_heartbeat.js";

/**
 * Agent slot heartbeat tools (issue #1402).
 *
 * Every agent tool that is already MCP-connected can announce it is alive
 * with a single `agent_heartbeat` call — no new HTTP client, no curl timer.
 * The dashboard (`/api/agents` on the Z.ai preview) and `agent_status` both
 * read the same Redis account, so pings show up in real time.
 *
 * Slot ↔ tool mapping (policy) lives in docs/master_docs/AGENT_SLOT_REGISTRY.yaml.
 * A tool MUST only ping its own assigned slot; pings are attributed with the
 * authenticated client id for auditability.
 */
export async function registerAgentTools(server: McpServer): Promise<void> {
  server.tool(
    "agent_heartbeat",
    "Announce that an agent tool is alive for its assigned slot (agent-N). Ping every 45s while running; the dashboard shows the slot as 🟢 online within 90s of the last ping.",
    {
      slot: z
        .string()
        .regex(/^agent-\d+$/, 'slot must match "agent-N" (e.g. "agent-4")')
        .describe("Assigned slot id from AGENT_SLOT_REGISTRY.yaml"),
      agentId: z
        .string()
        .min(1)
        .max(64)
        .optional()
        .describe("Human-readable tool label, e.g. 'Cline' (defaults to slot id)"),
    },
    async ({ slot, agentId }) => {
      try {
        const context = RequestContextStore.get();
        if (!context?.authenticated) {
          return {
            isError: true,
            content: [
              { type: "text", text: "Authentication required to ping a heartbeat" },
            ],
          };
        }
        const slotError = validateSlot(slot);
        if (slotError) {
          return { isError: true, content: [{ type: "text", text: slotError }] };
        }
        const result = await recordHeartbeat({
          slot,
          agentId,
          source: "mcp-tower",
          clientId: context.clientId,
        });
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error: ${(err as Error).message}` }],
        };
      }
    }
  );

  server.tool(
    "agent_status",
    "List live agent-slot heartbeats with derived real-time state: online (≤90s), stale (>90s, key alive), expired (no runtime signal).",
    {},
    async () => {
      try {
        const context = RequestContextStore.get();
        if (!context?.authenticated) {
          return {
            isError: true,
            content: [
              { type: "text", text: "Authentication required to read agent status" },
            ],
          };
        }
        const result = await listHeartbeats();
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      } catch (err) {
        return {
          isError: true,
          content: [{ type: "text", text: `Error: ${(err as Error).message}` }],
        };
      }
    }
  );
}
