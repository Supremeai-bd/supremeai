import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

// The public HF tiny-brain space (njelitltd-tiny-brain.hf.space) is dead.
// Tiny Brain tools are DISABLED unless the operator explicitly sets
// TINY_BRAIN_URL to a live, compatible deployment (e.g. the Render brain
// service). No dead endpoint is probed by default (unified training plan 0.4).
const DISABLED_TINY_BRAIN = {
  ok: false,
  disabled: true,
  reason:
    "Tiny Brain tools disabled: TINY_BRAIN_URL is not configured (the default HF space is retired).",
};

function getTinyBrainBaseUrl(): string | null {
  const url = (process.env.TINY_BRAIN_URL || "").trim().replace(/\/+$/, "");
  return url ? url : null;
}

export function registerTinyBrainTools(server: McpServer): void {
  // Both Tiny Brain calls may refresh provider state; do not advertise them as reads.
  server.tool(
    "tiny_brain.route",
    "Route a user prompt (Bangla/Banglish/English) via the configured Tiny Brain deployment (TINY_BRAIN_URL) to get intent, capability_tier, dispatch_mode, and top_available_ai. Disabled when TINY_BRAIN_URL is unset.",
    {
      prompt: z.string().min(1).describe("User prompt to classify and route"),
      context: z.string().optional().default("").describe("Optional short conversation context"),
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ prompt, context }) => {
      const base = getTinyBrainBaseUrl();
      if (!base) {
        return { content: [{ type: "text", text: JSON.stringify(DISABLED_TINY_BRAIN) }], isError: false };
      }
      const resp = await fetch(`${base}/route`, {
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
    "Get the ranked Top AI providers from the configured Tiny Brain deployment (TINY_BRAIN_URL). Disabled when TINY_BRAIN_URL is unset.",
    {
      force: z.boolean().optional().default(false).describe("Force an immediate probe refresh"),
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ force }) => {
      const base = getTinyBrainBaseUrl();
      if (!base) {
        return { content: [{ type: "text", text: JSON.stringify(DISABLED_TINY_BRAIN) }], isError: false };
      }
      const resp = await fetch(`${base}/top-ai?force=${force ? "true" : "false"}`);
      const text = await resp.text();
      return {
        content: [{ type: "text", text }],
        isError: !resp.ok,
      };
    },
  );

  server.tool(
    "kaggle_shadow.status",
    "Kaggle Shadow is disabled (phone verification unavailable).",
    {},
    { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    async () => {
      return {
        content: [{ type: "text", text: JSON.stringify({ ok: false, disabled: true, reason: "Kaggle Shadow disabled (phone verification unavailable)" }) }],
        isError: false,
      };
    },
  );
}
