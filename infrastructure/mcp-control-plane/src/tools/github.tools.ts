import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getWorkflowRuns, getFailedLogs, listSecrets } from "../adapters/github/index.js";

export async function registerGitHubTools(server: McpServer): Promise<void> {
  server.tool(
    "github.workflow_runs",
    "List recent GitHub Actions workflow runs for the repository.",
    {
      accountId: z.string().describe("The account ID (e.g. github-primary)"),
      limit: z.number().optional().describe("Number of runs to fetch (default: 5)"),
    },
    async ({ accountId, limit }) => {
      try {
        const runs = await getWorkflowRuns(accountId, limit || 5);
        return {
          content: [{ type: "text", text: JSON.stringify(runs, null, 2) }],
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
    "github.get_failed_logs",
    "Get the trailing logs for any failed jobs in a specific workflow run.",
    {
      accountId: z.string().describe("The account ID (e.g. github-primary)"),
      runId: z.string().describe("The GitHub Actions run ID"),
    },
    async ({ accountId, runId }) => {
      try {
        const logs = await getFailedLogs(accountId, runId);
        return {
          content: [{ type: "text", text: JSON.stringify(logs, null, 2) }],
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
    "github.list_secrets",
    "List all GitHub Actions secrets configured for the repository (names only).",
    {
      accountId: z.string().describe("The account ID (e.g. github-primary)"),
    },
    async ({ accountId }) => {
      try {
        const secrets = await listSecrets(accountId);
        return {
          content: [{ type: "text", text: JSON.stringify(secrets, null, 2) }],
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
