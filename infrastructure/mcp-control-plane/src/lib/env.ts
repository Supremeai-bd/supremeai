import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Type-safe environment loader.
 * Reads from process.env (injected by dotenv or Infisical at startup).
 * NEVER hardcodes values — only reads env var NAMES.
 */

function required(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`[env] Required env var missing: ${name}`);
  return v;
}

function optional(name: string, fallback = ""): string {
  return process.env[name] ?? fallback;
}

function multiKey(name: string): string[] {
  const v = optional(name);
  return v
    ? v
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean)
    : [];
}

export const env = {
  // ── MCP Server
  port: parseInt(optional("MCP_PORT", "3771")),
  mcpApiKey: optional("MCP_API_KEY"),
  nodeEnv: optional("NODE_ENV", "development"),

  // ── Render (4 accounts)
  render: {
    primary: {
      apiKey: optional("RENDER_API_KEY_1", optional("RENDER_API_KEY")),
      serviceId: optional("RENDER_PRIMARY_SVC_ID"),
      url: optional("RENDER_PRIMARY_URL"),
    },
    worker: {
      apiKey: optional("RENDER_API_KEY_2", optional("RENDER_API_KEY_BACKUP")),
      serviceId: optional("RENDER_WORKER_SVC_ID"),
      url: optional("RENDER_WORKER_URL"),
    },
    scraper: {
      apiKey: optional("RENDER_API_KEY_3", optional("RENDER_BACKUP_API_KEY_2")),
      serviceId: optional("RENDER_SCRAPER_SVC_ID"),
      url: optional("RENDER_SCRAPER_URL"),
    },
    controlTower: {
      apiKey: optional("RENDER_API_KEY_4"),
      serviceId: optional("RENDER_MCP_SVC_ID"),
      url: optional("RENDER_MCP_URL"),
    },
  },

  // ── Supabase
  supabase: {
    url: optional("SUPABASE_URL"),
    anonKey: optional("SUPABASE_KEY"),
    serviceRoleKey: optional("SUPABASE_SERVICE_ROLE_KEY"),
    dbUrl: optional("SUPABASE_DATABASE_URL"),
  },

  // ── Redis / Upstash (dual mode)
  redis: {
    restUrl: optional("UPSTASH_REDIS_REST_URL"),
    restToken: optional("UPSTASH_REDIS_REST_TOKEN"),
    url: optional("REDIS_URL"), // rediss:// protocol
  },

  // ── Infisical (machine identity — NOT token)
  infisical: {
    clientId: optional("INFISICAL_CLIENT_ID"),
    clientSecret: optional("INFISICAL_CLIENT_SECRET"),
    projectId: optional("INFISICAL_PROJECT_ID"),
    environment: optional("INFISICAL_ENVIRONMENT", "production"),
  },

  // ── GitHub
  github: {
    token: optional("GITHUB_TOKEN", optional("GITHUB_API_TOKEN")),
    repo: optional("GITHUB_REPO", "SaifulHaqueNiloy/supremeai"),
  },

  // ── Cloudflare
  cloudflare: {
    apiToken: process.env.CLOUDFLARE_API_TOKEN,
    accountId: process.env.CLOUDFLARE_ACCOUNT_ID,
    zoneId: process.env.CLOUDFLARE_ZONE_ID,
    workerUrl: process.env.CLOUDFLARE_WORKER_URL,
  },

  // ── Firebase (SA key loaded from Infisical at runtime — not from file)
  firebase: {
    serviceAccountJson: optional("FIREBASE_SERVICE_ACCOUNT_JSON"),
    projectId: optional("GCP_PROJECT_ID", "supremeai-a"),
  },

  // ── AI Providers (comma-separated multi-key pools)
  ai: {
    geminiKeys: multiKey("GEMINI_API_KEY"),
    groqKeys: multiKey("GROQ_API_KEY"),
    openrouterKeys: multiKey("OPENROUTER_API_KEY"),
    githubModelsKeys: multiKey("GITHUB_MODELS_API_KEY"),
    mistralKey: optional("MISTRAL_API_KEY"),
  },

  // ── Kaggle (6-account pool)
  kaggle: {
    tokens: multiKey("KAGGLE_API_TOKENS"),
  },

  // ── Notifications
  notify: {
    telegramBotToken: optional("TELEGRAM_BOT_TOKEN"),
    telegramChatId: optional("TELEGRAM_CHAT_ID"),
    discordWebhookUrl: optional("DISCORD_WEBHOOK_URL"),
  },

  // ── Stripe
  stripe: {
    secretKey: optional("STRIPE_SECRET_KEY"),
    webhookSecret: optional("STRIPE_WEBHOOK_SECRET"),
  },

  // ── Qdrant
  qdrant: {
    url: optional("QDRANT_URL"),
    apiKey: optional("QDRANT_API_KEY"),
  },

  // ── Vercel
  vercel: {
    token: optional("VERCEL_TOKEN"),
    projectId: optional("VERCEL_PROJECT_ID"),
  },

  // ── Firecrawl
  firecrawl: {
    apiKeys: multiKey("FIRECRAWL_API_KEY"),
  },
};

export type Env = typeof env;
