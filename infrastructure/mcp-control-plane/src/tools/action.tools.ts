import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { globalActionExecutor } from "../actions/executor.js";
import { buildRenderDeployAction } from "../adapters/render/actions.js";
import { buildRedisFlushAction } from "../adapters/redis/actions.js";
import { buildCloudflarePurgeCacheAction } from "../adapters/cloudflare/actions.js";

export async function registerActionTools(server: McpServer): Promise<void> {
  server.tool(
    "action.render_deploy",
    "Trigger a Render service deployment. Pass 'overrideRequestId' if you are executing an already-approved HITL request.",
    {
      serviceId: z.string().describe("Render Service ID"),
      clearCache: z.boolean().optional().describe("Whether to clear build cache"),
      confirm: z.boolean().optional().default(false).describe("Must be true to execute (destructive guard)"),
      dry_run: z.boolean().optional().default(false).describe("If true, return the plan without executing"),
      overrideRequestId: z.string().optional().describe("Approved Request ID to bypass policy engine")
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false },
    async ({ serviceId, clearCache, confirm, dry_run, overrideRequestId }) => {
      try {
        const plan = buildRenderDeployAction(serviceId, clearCache);
        if (dry_run) {
          return { content: [{ type: "text", text: JSON.stringify({ dry_run: true, plan }, null, 2) }] };
        }
        if (!confirm) {
          return { isError: true, content: [{ type: "text", text: "confirm must be true to execute action.render_deploy" }] };
        }
        const result = await globalActionExecutor.execute(plan, overrideRequestId);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      } catch (err: any) {
        return { isError: true, content: [{ type: "text", text: err.message }] };
      }
    }
  );

  server.tool(
    "action.redis_flush",
    "Flush Redis cache (optionally by prefix). Pass 'overrideRequestId' if you are executing an already-approved HITL request.",
    {
      prefix: z.string().optional().describe("Prefix to match keys. If empty, flushes all."),
      confirm: z.boolean().optional().default(false).describe("Must be true to execute (destructive guard)"),
      dry_run: z.boolean().optional().default(false).describe("If true, return the plan without executing"),
      overrideRequestId: z.string().optional().describe("Approved Request ID to bypass policy engine")
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ prefix, confirm, dry_run, overrideRequestId }) => {
      try {
        const plan = buildRedisFlushAction(prefix);
        if (dry_run) {
          return { content: [{ type: "text", text: JSON.stringify({ dry_run: true, plan }, null, 2) }] };
        }
        if (!confirm) {
          return { isError: true, content: [{ type: "text", text: "confirm must be true to execute action.redis_flush" }] };
        }
        const result = await globalActionExecutor.execute(plan, overrideRequestId);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      } catch (err: any) {
        return { isError: true, content: [{ type: "text", text: err.message }] };
      }
    }
  );

  server.tool(
    "action.cloudflare_purge",
    "Purge Cloudflare Cache. Pass 'overrideRequestId' if you are executing an already-approved HITL request.",
    {
      confirm: z.boolean().optional().default(false).describe("Must be true to execute (destructive guard)"),
      dry_run: z.boolean().optional().default(false).describe("If true, return the plan without executing"),
      overrideRequestId: z.string().optional().describe("Approved Request ID to bypass policy engine")
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ confirm, dry_run, overrideRequestId }) => {
      try {
        const plan = buildCloudflarePurgeCacheAction();
        if (dry_run) {
          return { content: [{ type: "text", text: JSON.stringify({ dry_run: true, plan }, null, 2) }] };
        }
        if (!confirm) {
          return { isError: true, content: [{ type: "text", text: "confirm must be true to execute action.cloudflare_purge" }] };
        }
        const result = await globalActionExecutor.execute(plan, overrideRequestId);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      } catch (err: any) {
        return { isError: true, content: [{ type: "text", text: err.message }] };
      }
    }
  );
}
