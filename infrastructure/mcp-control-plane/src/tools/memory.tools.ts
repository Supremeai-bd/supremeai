/**
 * Memory Tools — dynamic bridge of ALL Python Memory Server tools
 * into the Control Tower under the `memory.*` prefix.
 *
 * 100% dynamic: tool list comes from MemorySubAdapter.listTools()
 * (live MCP discovery). Falls back to a static snapshot so the gateway
 * still advertises memory tools while the sidecar is cold-starting.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { MemorySubAdapter } from "../adapters/memory/index.js";
import { jsonSchemaToZodShape } from "../adapters/memory/jsonSchemaToZod.js";

/** Static fallback: mirrors backend/memory/mcp_server.py tool names. */
const FALLBACK_TOOLS: Array<{ name: string; description: string }> = [
  { name: "create_entities", description: "Create entities in the Knowledge Graph." },
  { name: "create_relations", description: "Create directed relations between entities." },
  { name: "add_observations", description: "Add observations to an existing entity." },
  { name: "delete_entities", description: "Delete entities and their relations." },
  { name: "delete_observations", description: "Remove observations from an entity." },
  { name: "delete_relations", description: "Delete specific relations." },
  { name: "read_graph", description: "Return the entire Knowledge Graph." },
  { name: "search_nodes", description: "Search Knowledge Graph nodes." },
  { name: "open_nodes", description: "Open specific nodes and relations." },
  { name: "store_document", description: "Store a document in the vector store." },
  { name: "search_semantic", description: "Semantic search over vector store." },
  { name: "ingest_document_rag", description: "Chunk + ingest a document into RAG." },
  { name: "record_task", description: "Record a task execution into episodic memory." },
  { name: "get_similar_tasks", description: "Retrieve similar past task executions." },
  { name: "get_recent_episodes", description: "Retrieve recent episodic records." },
  { name: "build_context", description: "Build token-budget-aware context string." },
  { name: "get_session_stats", description: "Sliding window stats for a session." },
  { name: "clear_session", description: "Clear sliding window memory for a session." },
  { name: "remember_fact", description: "Save a long-term fact (Supabase/SQLite)." },
  { name: "search_learned_facts", description: "Search stored long-term facts." },
];

export async function registerMemoryTools(
  server: McpServer,
  adapter: MemorySubAdapter,
): Promise<void> {
  // Eager sidecar start (non-blocking): kick off the Python process NOW so
  // that by the time the IDE finishes its handshake + tool listing, the
  // live inventory is ready. listTools() below awaits the same promise.
  const eagerStart = adapter.start().catch(() => undefined);
  let discovered = await adapter.listTools();
  await eagerStart;

  // Use live inventory when available; otherwise emit the fallback snapshot.
  const tools = discovered.length > 0 ? discovered : FALLBACK_TOOLS;

  for (const tool of tools) {
    const exposed = "memory." + tool.name;
    const shape = jsonSchemaToZodShape(tool.inputSchema);
    const desc = (tool.description ?? "Memory tool: " + tool.name) +
      " [proxied to Python memory sidecar as '" + tool.name + "']";

    server.tool(exposed, desc, shape, async (rawArgs: unknown) => {
      const args = (rawArgs ?? {}) as Record<string, unknown>;
      try {
        const res = await adapter.callTool(tool.name, args);
        if (res.ok) {
          const text = typeof res.data === "string"
            ? res.data : JSON.stringify(res.data ?? null, null, 2);
          return { content: [{ type: "text", text }] };
        }
        return {
          isError: !res.transient ? true : undefined,
          content: [{ type: "text", text: "Error: " + (res.error ?? "unknown") }],
        };
      } catch (err) {
        return {
          content: [{ type: "text", text: "Error: " + (err as Error).message }],
        };
      }
    });
  }

  server.tool(
    "memory.status",
    "Health of the internal Python memory sidecar (ready/starting, tool count, last error).",
    {},
    async () => {
      const tools = await adapter.listTools();
      const payload = {
        ready: adapter.isReady,
        toolCount: tools.length > 0 ? tools.length : FALLBACK_TOOLS.length,
        startAttempts: adapter.attemptCount,
        lastError: adapter.lastFailure,
      };
      return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }] };
    },
  );

  // Keep unused import referenced for strict builds.
  void z;
}
