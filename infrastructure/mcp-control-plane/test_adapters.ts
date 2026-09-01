import "dotenv/config";
import { listServices, getServiceHealth } from "./src/adapters/render/index.js";
import { getWorkflowRuns, listSecrets } from "./src/adapters/github/index.js";
import { getHealth, getAuthUsers } from "./src/adapters/supabase/index.js";
import * as path from "node:path";
import * as fs from "node:fs";
import { config } from "dotenv";

config({ path: path.resolve(process.cwd(), "../../.env") });

async function main() {
  console.log("=== Testing Render Adapter ===");
  try {
    const renderPrimaryId = "render-primary";
    const services = await listServices(renderPrimaryId) as any[];
    console.log(`[Render] Found ${services.length} services on ${renderPrimaryId}`);
    if (services.length > 0) {
      const firstService = services[0].service.id;
      const health = await getServiceHealth(renderPrimaryId, firstService);
      console.log(`[Render] Health for ${firstService}:`, JSON.stringify(health).slice(0, 100) + "...");
    }
  } catch (e) {
    console.error("[Render] Error:", (e as Error).message);
  }

  console.log("\n=== Testing GitHub Adapter ===");
  try {
    const githubId = "github-primary";
    const runs = await getWorkflowRuns(githubId, 1) as any;
    console.log(`[GitHub] Latest runs:`, runs.total_count || "Unknown");
    const secrets = await listSecrets(githubId) as any;
    console.log(`[GitHub] Total secrets:`, secrets.total_count || "Unknown");
  } catch (e) {
    console.error("[GitHub] Error:", (e as Error).message);
  }

  console.log("\n=== Testing Supabase Adapter ===");
  try {
    const supabaseId = "supabase-primary";
    const health = await getHealth(supabaseId);
    console.log(`[Supabase] Health:`, health);
    const users = await getAuthUsers(supabaseId);
    console.log(`[Supabase] Auth users:`, users);
  } catch (e) {
    console.error("[Supabase] Error:", (e as Error).message);
  }
}

main().catch(console.error);
