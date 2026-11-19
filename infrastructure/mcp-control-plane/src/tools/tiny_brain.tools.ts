import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const DEFAULT_TINY_BRAIN_URL = "https://njelitltd-tiny-brain.hf.space";
const DEFAULT_KAGGLE_SHADOW_URL = "https://supremeai-kaggle-mcp.paykaribazaronline.workers.dev";

function getTinyBrainBaseUrl(): string {
  return (process.env.TINY_BRAIN_URL || DEFAULT_TINY_BRAIN_URL).replace(/\/+$/, "");
}

export function registerTinyBrainTools(server: McpServer): void {
  server.tool(
    "tiny_brain.route",
    "Route a user prompt (Bangla/Banglish/English) via Hugging Face Tiny Brain to get intent, capability_tier, dispatch_mode, and top_available_ai.",
    {
      prompt: z.string().min(1).describe("User prompt to classify and route"),
      context: z.string().optional().default("").describe("Optional short conversation context"),
    },
    async ({ prompt, context }) => {
      const resp = await fetch(`${getTinyBrainBaseUrl()}/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, context }),
      });
      const text = await resp.text();
      return {
        content: [{ type: "text", text }],
        isError: !resp.ok,
      };
    },
  );

  server.tool(
    "tiny_brain.top_ai",
    "Get the ranked Top AI providers from the Hugging Face Tiny Brain Hybrid Top AI Detector.",
    {
      force: z.boolean().optional().default(false).describe("Force an immediate probe refresh"),
    },
    async ({ force }) => {
      const resp = await fetch(`${getTinyBrainBaseUrl()}/top-ai?force=${force ? "true" : "false"}`);
      const text = await resp.text();
      return {
        content: [{ type: "text", text }],
        isError: !resp.ok,
      };
    },
  );

  server.tool(
    "kaggle_shadow.status",
    "Check which Kaggle account and shadow node URL is currently active in the 24/7 Cloudflare-Kaggle rotator.",
    {},
    async () => {
      const baseUrl = (process.env.KAGGLE_SHADOW_URL || DEFAULT_KAGGLE_SHADOW_URL).replace(/\/+$/, "");
      const resp = await fetch(`${baseUrl}/status`, {
        headers: { "User-Agent": "SupremeAI-MCP-Tower/1.0" },
      });
      const text = await resp.text();
      return {
        content: [{ type: "text", text }],
        isError: !resp.ok,
      };
    },
  );
}
