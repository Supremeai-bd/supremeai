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
  get port(): number { return parseInt(optional("MCP_PORT", "3771")); },
  get mcpApiKey(): string { return optional("MCP_API_KEY"); },
  get mcpAdminKey(): string { return optional("MCP_ADMIN_KEY", optional("MCP_API_KEY")); },
  get mcpViewerKey(): string { return optional("MCP_VIEWER_KEY"); },
  get mcpAgentKey(): string { return optional("MCP_AGENT_KEY"); },
  get githubWebhookSecret(): string { return optional("GITHUB_WEBHOOK_SECRET"); },
  get cloudflareWebhookSecret(): string { return optional("CLOUDFLARE_WEBHOOK_SECRET"); },
  get nodeEnv(): string { return optional("NODE_ENV", "development"); },

  // ── Render (4 accounts)
  render: {
    primary: {
      get apiKey(): string { return optional("RENDER_API_KEY_1", optional("RENDER_API_KEY")); },
      get serviceId(): string { return optional("RENDER_PRIMARY_SVC_ID"); },
      get url(): string { return optional("RENDER_PRIMARY_URL"); },
    },
    worker: {
      get apiKey(): string { return optional("RENDER_API_KEY_2", optional("RENDER_API_KEY_BACKUP")); },
      get serviceId(): string { return optional("RENDER_WORKER_SVC_ID"); },
      get url(): string { return optional("RENDER_WORKER_URL"); },
    },
    scraper: {
      get apiKey(): string { return optional("RENDER_API_KEY_3", optional("RENDER_BACKUP_API_KEY_2")); },
      get serviceId(): string { return optional("RENDER_SCRAPER_SVC_ID"); },
      get url(): string { return optional("RENDER_SCRAPER_URL"); },
    },
    controlTower: {
      get apiKey(): string { return optional("RENDER_API_KEY_4"); },
      get serviceId(): string { return optional("RENDER_MCP_SVC_ID"); },
      get url(): string { return optional("RENDER_MCP_URL"); },
    },
  },

  // ── Supabase
  supabase: {
    get url(): string { return optional("SUPABASE_URL"); },
    get anonKey(): string { return optional("SUPABASE_KEY"); },
    get serviceRoleKey(): string { return optional("SUPABASE_SERVICE_ROLE_KEY"); },
    get dbUrl(): string { return optional("SUPABASE_DATABASE_URL"); },
  },

  // ── Redis / Upstash (dual mode)
  redis: {
    get restUrl(): string { return optional("UPSTASH_REDIS_REST_URL"); },
    get restToken(): string { return optional("UPSTASH_REDIS_REST_TOKEN"); },
    get url(): string { return optional("REDIS_URL"); }, // rediss:// protocol
  },

  // ── Infisical (machine identity — NOT token)
  infisical: {
    get clientId(): string { return optional("INFISICAL_CLIENT_ID"); },
    get clientSecret(): string { return optional("INFISICAL_CLIENT_SECRET"); },
    get projectId(): string { return optional("INFISICAL_PROJECT_ID"); },
    get environment(): string { return optional("INFISICAL_ENVIRONMENT", "production"); },
  },

  // ── GitHub
  github: {
    get token(): string { return optional("GITHUB_TOKEN", optional("GITHUB_API_TOKEN")); },
    get repo(): string { return optional("GITHUB_REPO", "SaifulHaqueNiloy/supremeai"); },
  },

  // ── Cloudflare
  cloudflare: {
    get apiToken(): string | undefined { return process.env.CLOUDFLARE_API_TOKEN; },
    get accountId(): string | undefined { return process.env.CLOUDFLARE_ACCOUNT_ID; },
    get zoneId(): string | undefined { return process.env.CLOUDFLARE_ZONE_ID; },
    get workerUrl(): string | undefined { return process.env.CLOUDFLARE_WORKER_URL || process.env.SUPREMEAI_CF_WORKER_URL; },
  },

  // ── Firebase (SA key loaded from Infisical at runtime — not from file)
  firebase: {
    get serviceAccountJson(): string { return optional("FIREBASE_SERVICE_ACCOUNT_JSON"); },
    get projectId(): string { return optional("GCP_PROJECT_ID", "supremeai-a"); },
  },

  // ── AI Providers (comma-separated multi-key pools)
  ai: {
    get geminiModel(): string { return optional("MCP_GEMINI_MODEL", "gemini-2.0-flash"); },
    get groqModel(): string { return optional("MCP_GROQ_MODEL", "llama-3.3-70b-versatile"); },
    get openrouterModel(): string { return optional("MCP_OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"); },
    get githubModel(): string { return optional("MCP_GITHUB_MODEL", "gpt-4o-mini"); },
    get mistralModel(): string { return optional("MCP_MISTRAL_MODEL", "mistral-small-latest"); },
    get geminiKeys(): string[] { return multiKey("GEMINI_API_KEY"); },
    get groqKeys(): string[] { return multiKey("GROQ_API_KEY"); },
    get openrouterKeys(): string[] { return multiKey("OPENROUTER_API_KEY"); },
    get githubModelsKeys(): string[] { return multiKey("GITHUB_MODELS_API_KEY"); },
    get mistralKey(): string { return optional("MISTRAL_API_KEY"); },
  },

  // ── Kaggle (6-account pool)
  kaggle: {
    get tokens(): string[] {
      const explicit = multiKey("KAGGLE_API_TOKENS");
      if (explicit.length > 0) return explicit;
      const collected: string[] = [];
      for (let i = 1; i <= 6; i++) {
        const val = optional(`KAGGLE_API_TOKEN_${i}`);
        if (val) collected.push(val);
      }
      const single = optional("KAGGLE_API_TOKEN");
      if (single) collected.push(single);
      return collected;
    },
  },

  // ── Notifications
  notify: {
    get telegramBotToken(): string { return optional("TELEGRAM_BOT_TOKEN"); },
    get telegramChatId(): string { return optional("TELEGRAM_CHAT_ID"); },
    get discordWebhookUrl(): string { return optional("DISCORD_WEBHOOK_URL"); },
  },

  // ── Stripe
  stripe: {
    get secretKey(): string { return optional("STRIPE_SECRET_KEY"); },
    get webhookSecret(): string { return optional("STRIPE_WEBHOOK_SECRET"); },
  },

  // ── Qdrant
  qdrant: {
    get url(): string { return optional("QDRANT_URL"); },
    get apiKey(): string { return optional("QDRANT_API_KEY"); },
  },

  // ── Vercel
  vercel: {
    get token(): string { return optional("VERCEL_TOKEN"); },
    get projectId(): string { return optional("VERCEL_PROJECT_ID"); },
  },

  // ── Firecrawl
  firecrawl: {
    get apiKeys(): string[] { return multiKey("FIRECRAWL_API_KEY"); },
  },
};

export type Env = typeof env;


