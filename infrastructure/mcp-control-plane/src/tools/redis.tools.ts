import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { pingRedis, getRedisStats } from "../adapters/redis/index.js";

export async function registerRedisTools(server: McpServer): Promise<void> {
  server.tool(
    "redis.ping",
    "Ping the Redis cache/queue to verify connectivity.",
    {},
    async () => {
      try {
        const res = await pingRedis();
        return {
          content: [{ type: "text", text: JSON.stringify(res, null, 2) }],
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
    "redis.stats",
    "Get basic statistics from Redis via the INFO command.",
    {},
    async () => {
      try {
        const stats = await getRedisStats();
        return {
          content: [{ type: "text", text: JSON.stringify(stats, null, 2) }],
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
