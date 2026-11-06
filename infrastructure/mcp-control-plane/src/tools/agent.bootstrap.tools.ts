import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import * as fs from "node:fs";
import * as path from "node:path";

/**
 * Universal Agent Context Bootstrap Tool
 * Provides connected AI agents with an instant, token-efficient, authoritative summary
 * of project invariants, repository topology, and core rules without crawling hundreds of files.
 */
export async function registerAgentBootstrapTools(server: McpServer): Promise<void> {
  server.tool(
    "agent_context_bootstrap",
    "Instantly bootstrap an AI agent with SupremeAI's core architecture, 5 Universal Invariants, 2-repository topology, active endpoints, and PR submission rules in a single call.",
    {
      scope: z
        .enum(["all", "invariants", "topology", "endpoints"])
        .optional()
        .default("all")
        .describe("Which section of the bootstrap context to retrieve"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ scope }) => {
      const summary: Record<string, any> = {
        project: "SupremeAI 2.0",
        version: "1.0.1",
        timestamp: new Date().toISOString(),
      };

      if (scope === "all" || scope === "topology") {
        summary.topology = {
          model: "Pure 2-Repository Topology",
          primaryMonorepo: "Supremeai-bd/supremeai (Unified Monorepo SSOT: Core, Gateway, Browser, VSCode, Studio, Infrastructure)",
          cockpitRepo: "Supremeai-bd/supremeai-studio (Public UI & Mission Control)",
          retiredSatellites: [
            "supremeai-core (Archived)",
            "supremeai-api (Archived)",
            "supremeai-browser (Archived)",
            "supremeai-vscode (Archived)",
            "supremeai-open (Deleted)",
          ],
        };
      }

      if (scope === "all" || scope === "invariants") {
        summary.universalInvariants = [
          "1. Dual-Rebase: Rebase origin/main at work-start and pre-push (0 behind).",
          "2. Boundary Integrity: No code in repo root (`src/*`, `packages/*`). Satellites live in studio/*, core/*, etc.",
          "3. 3-Tier Verification: Every PR must include Reflection Evidence (why + alternatives_rejected) and test proof.",
          "4. Fail-Closed Stale Base Pin: When submitting full_file patches, declare current baseSha.",
          "5. Occam's Razor & Anti-Bloat: Deliver the minimal, simplest solution. No over-engineering.",
          "6. Atomic Completeness: Do not fragment interdependent fixes into multiple broken micro-PRs.",
        ];
      }

      if (scope === "all" || scope === "endpoints") {
        summary.endpoints = {
          mcpControlTower: "https://supremeai-mcp-tower.onrender.com",
          supabaseProject: "https://xtvkltzmberxekoamala.supabase.co",
          cloudflareWorker: "https://supremeai-keepwarm-worker (Edge Mesh)",
          authProvider: "Supabase Native Auth (Zero-Firebase)",
        };
      }

      summary.prSubmissionGuidelines = {
        prBodySections: [
          "## Reflection Evidence (why + alternatives_rejected)",
          "## 3-Tier Verify & Test Evidence",
          "Closes #<issue_number>",
        ],
        preflightCommand: "python scripts/ci/pr_preflight_guard.py --branch <name> --files <files...>",
      };

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(summary, null, 2),
          },
        ],
      };
    }
  );
}

