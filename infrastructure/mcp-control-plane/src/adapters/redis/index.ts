import { env } from "../../lib/env.js";
import { Redis as UpstashRedis } from "@upstash/redis";
import Redis from "ioredis";

type RedisClientInfo = {
  mode: "upstash-rest" | "ioredis-tcp";
  ping: () => Promise<string>;
  info: () => Promise<string>;
};

function getClient(): RedisClientInfo {
  // Mode A: Upstash REST
  if (env.redis.restUrl && env.redis.restToken) {
    const redis = new UpstashRedis({
      url: env.redis.restUrl,
      token: env.redis.restToken,
    });
    return {
      mode: "upstash-rest",
      ping: async () => await redis.ping(),
      info: async () => {
        // Upstash doesn't fully support raw INFO command, but we can try
        try {
          // @ts-ignore
          const res = await redis.info();
          return typeof res === "string" ? res : JSON.stringify(res);
        } catch {
          return "INFO command not fully supported on Upstash REST cache.";
        }
      },
    };
  }

  // Mode B: TCP Fallback
  if (env.redis.url) {
    const redisClient = new (Redis as any)(env.redis.url, {
      maxRetriesPerRequest: 1,
      connectTimeout: 5000,
    });
    return {
      mode: "ioredis-tcp",
      ping: async () => await redisClient.ping(),
      info: async () => {
        const infoStr = await redisClient.info();
        redisClient.disconnect();
        return infoStr;
      },
    };
  }

  throw new Error("No Redis configuration found (missing REST or TCP credentials)");
}

export async function pingRedis(): Promise<unknown> {
  const client = getClient();
  const start = Date.now();
  const res = await client.ping();
  return {
    mode: client.mode,
    status: res,
    latencyMs: Date.now() - start,
  };
}

export async function getRedisStats(): Promise<unknown> {
  const client = getClient();
  const info = await client.info();
  return {
    mode: client.mode,
    statsRaw: info,
  };
}
