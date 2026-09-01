import "dotenv/config";
import * as path from "node:path";
import { config } from "dotenv";

config({ path: path.resolve(process.cwd(), "../../.env") });

import { registerSystemSummaryTools } from "./src/tools/system.summary.tools.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

async function main() {
  const server = new McpServer({ name: "test", version: "1.0.0" });
  await registerSystemSummaryTools(server);
  
  // Note: we can't easily extract the tool function natively from McpServer without casting
  // Instead, let's just run the code directly that system.summary runs.
  const { getServiceHealth } from "./src/adapters/render/index.js";
  const { getHealth: getSupabaseHealth } from "./src/adapters/supabase/index.js";
  const { pingRedis } = await import("./src/adapters/redis/index.js");
  // Just importing them runs no risk.
  
  console.log("Registered system.summary tool. Run full MCP server to test.");
}

main().catch(console.error);
