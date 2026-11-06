import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { harnessAdapter } from "../adapters/harness/index.js";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";

function assertHarnessAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) {
    return null;
  }
  if (roleRank(store.role) < roleRank(minRole)) {
    return `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
  }
  return null;
}

export function registerHarnessTools(server: McpServer): void {
  // 1. harness.ping
  server.tool(
    "harness.ping",
    "Check connectivity and access to the Harness Next-Gen platform.",
    {},
    async () => {
      const err = assertHarnessAccess("harness.ping", "viewer");
      if (err) return { content: [{ type: "text", text: err }] };

      const res = await harnessAdapter.ping();
      return { content: [{ type: "text", text: JSON.stringify(res, null, 2) }] };
    }
  );

  // 2. harness.pipeline_status
  server.tool(
    "harness.pipeline_status",
    "Query execution status of a Harness deployment or verification pipeline.",
    {
      executionId: z.string().describe("The execution UUID to inspect"),
    },
    async ({ executionId }) => {
      const err = assertHarnessAccess("harness.pipeline_status", "viewer");
      if (err) return { content: [{ type: "text", text: err }] };

      const status = await harnessAdapter.getExecutionStatus(executionId);
      return { content: [{ type: "text", text: JSON.stringify(status, null, 2) }] };
    }
  );

  // 3. harness.list_environments
  server.tool(
    "harness.list_environments",
    "List registered deployment environments in Harness (e.g. Production).",
    {},
    async () => {
      const err = assertHarnessAccess("harness.list_environments", "viewer");
      if (err) return { content: [{ type: "text", text: err }] };

      const envs = await harnessAdapter.listEnvironments();
      return { content: [{ type: "text", text: JSON.stringify(envs, null, 2) }] };
    }
  );
}
