import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listProviders, testProvider } from "../adapters/ai/index.js";

export async function registerAITools(server: McpServer): Promise<void> {
  server.tool(
    "ai.list_providers",
    "List all configured AI providers and the number of keys available in their pools.",
    {},
    async () => {
      try {
        const providers = listProviders();
        return {
          content: [{ type: "text", text: JSON.stringify(providers, null, 2) }],
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
    "ai.test_provider",
    "Test an AI provider's API to ensure the keys in the pool are valid and working (tests models endpoint).",
    {
      provider: z.string().describe("The provider to test, e.g. gemini, groq, openrouter, github, mistral"),
    },
    async ({ provider }) => {
      try {
        const result = await testProvider(provider);
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
