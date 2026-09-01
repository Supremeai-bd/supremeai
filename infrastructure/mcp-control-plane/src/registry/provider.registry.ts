import { env } from "../lib/env.js";

/**
 * Provider Registry — the source of truth for all connected services.
 * No hardcoded account IDs, URLs, or credentials.
 * All values resolved from env refs at runtime.
 */

export type ProviderName =
  | "render"
  | "github"
  | "supabase"
  | "redis"
  | "cloudflare"
  | "infisical"
  | "firebase"
  | "ai"
  | "kaggle"
  | "stripe"
  | "qdrant"
  | "vercel"
  | "firecrawl"
  | "telegram"
  | "discord";

export type Capability =
  | "health"
  | "logs"
  | "metrics"
  | "deploy"
  | "restart"
  | "rollback"
  | "env_vars"
  | "secrets"
  | "notify"
  | "ai_inference"
  | "storage"
  | "auth";

export interface ProviderAccount {
  id: string;
  provider: ProviderName;
  displayName: string;
  role: string;
  environment: "production" | "staging" | "development";
  capabilities: Capability[];
  /** Env var name for API key — NOT the value itself */
  apiKeyRef: string;
  /** Optional: URL or endpoint */
  url?: string;
  /** Optional: service/resource ID */
  serviceId?: string;
  /** Is this account available? (key present in env) */
  available: boolean;
}

function isAvailable(envRef: string): boolean {
  const val = process.env[envRef] ?? "";
  return val.length > 0;
}

/**
 * Registry is built dynamically from env at startup.
 * Adding a new account = add env vars + add entry here.
 */
export function buildRegistry(): ProviderAccount[] {
  return [
    // ── Render ──────────────────────────────────────────
    {
      id: "render-primary",
      provider: "render",
      displayName: "Render Primary (Core API)",
      role: "core-api",
      environment: "production",
      capabilities: ["health", "logs", "deploy", "restart", "env_vars"],
      apiKeyRef: "RENDER_API_KEY_1",
      url: env.render.primary.url || "https://supremeai-primary-node.onrender.com",
      serviceId: env.render.primary.serviceId,
      available: isAvailable("RENDER_API_KEY_1") || isAvailable("RENDER_API_KEY"),
    },
    {
      id: "render-worker",
      provider: "render",
      displayName: "Render Worker (Async Tasks)",
      role: "async-worker",
      environment: "production",
      capabilities: ["health", "logs", "deploy", "restart", "env_vars"],
      apiKeyRef: "RENDER_API_KEY_2",
      url: env.render.worker.url || "https://supremeai-worker-node.onrender.com",
      serviceId: env.render.worker.serviceId,
      available: isAvailable("RENDER_API_KEY_2") || isAvailable("RENDER_API_KEY_BACKUP"),
    },
    {
      id: "render-scraper",
      provider: "render",
      displayName: "Render Scraper (Browser/Scraping)",
      role: "browser-scraper",
      environment: "production",
      capabilities: ["health", "logs", "deploy", "restart", "env_vars"],
      apiKeyRef: "RENDER_API_KEY_3",
      url: env.render.scraper.url || "https://supremeai-scraper-node.onrender.com",
      serviceId: env.render.scraper.serviceId,
      available: isAvailable("RENDER_API_KEY_3") || isAvailable("RENDER_BACKUP_API_KEY_2"),
    },
    {
      id: "render-mcp",
      provider: "render",
      displayName: "Render MCP (Control Tower)",
      role: "mcp-server",
      environment: "production",
      capabilities: ["health", "logs", "deploy", "restart", "env_vars"],
      apiKeyRef: "RENDER_API_KEY_4",
      url: env.render.controlTower.url || "https://supremeai-mcp.onrender.com",
      serviceId: env.render.controlTower.serviceId,
      available: isAvailable("RENDER_API_KEY_4"),
    },

    // ── GitHub ──────────────────────────────────────────
    {
      id: "github-main",
      provider: "github",
      displayName: "GitHub (SaifulHaqueNiloy/supremeai)",
      role: "ci-cd",
      environment: "production",
      capabilities: ["logs", "deploy"],
      apiKeyRef: "GITHUB_API_TOKEN",
      url: "https://api.github.com",
      available: isAvailable("GITHUB_API_TOKEN") || isAvailable("GITHUB_TOKEN"),
    },

    // ── Supabase ────────────────────────────────────────
    {
      id: "supabase-primary",
      provider: "supabase",
      displayName: "Supabase Primary DB (Singapore)",
      role: "primary-db",
      environment: "production",
      capabilities: ["health", "metrics", "storage"],
      apiKeyRef: "SUPABASE_KEY",
      url: env.supabase.url,
      available: isAvailable("SUPABASE_URL") && isAvailable("SUPABASE_KEY"),
    },

    // ── Redis (Upstash) ─────────────────────────────────
    {
      id: "redis-upstash",
      provider: "redis",
      displayName: "Upstash Redis (REST API)",
      role: "cache",
      environment: "production",
      capabilities: ["health", "metrics"],
      apiKeyRef: "UPSTASH_REDIS_REST_TOKEN",
      url: env.redis.restUrl,
      available: isAvailable("UPSTASH_REDIS_REST_URL") && isAvailable("UPSTASH_REDIS_REST_TOKEN"),
    },

    // ── Cloudflare ──────────────────────────────────────
    {
      id: "cloudflare-worker",
      provider: "cloudflare",
      displayName: "Cloudflare Worker (Edge/Ping)",
      role: "edge-gateway",
      environment: "production",
      capabilities: ["health", "metrics"],
      apiKeyRef: "CLOUDFLARE_API_TOKEN",
      url: env.cloudflare.workerUrl,
      available: isAvailable("CLOUDFLARE_API_TOKEN") || isAvailable("CLOUDFLARE_WORKERS_API_TOKEN"),
    },

    // ── Infisical ───────────────────────────────────────
    {
      id: "infisical-vault",
      provider: "infisical",
      displayName: "Infisical Secret Vault",
      role: "secrets",
      environment: "production",
      capabilities: ["secrets"],
      apiKeyRef: "INFISICAL_CLIENT_SECRET",
      available: isAvailable("INFISICAL_CLIENT_ID") && isAvailable("INFISICAL_CLIENT_SECRET"),
    },

    // ── Firebase ────────────────────────────────────────
    {
      id: "firebase-supremeai-a",
      provider: "firebase",
      displayName: "Firebase (supremeai-a)",
      role: "auth-hosting",
      environment: "production",
      capabilities: ["health", "auth"],
      apiKeyRef: "FIREBASE_SERVICE_ACCOUNT_JSON",
      available: isAvailable("FIREBASE_SERVICE_ACCOUNT_JSON"),
    },

    // ── AI Providers ────────────────────────────────────
    {
      id: "ai-gemini",
      provider: "ai",
      displayName: `Gemini (${(process.env["GEMINI_API_KEY"] ?? "").split(",").filter(Boolean).length} keys)`,
      role: "ai-inference",
      environment: "production",
      capabilities: ["ai_inference"],
      apiKeyRef: "GEMINI_API_KEY",
      available: isAvailable("GEMINI_API_KEY"),
    },
    {
      id: "ai-groq",
      provider: "ai",
      displayName: `Groq (${(process.env["GROQ_API_KEY"] ?? "").split(",").filter(Boolean).length} keys)`,
      role: "ai-inference",
      environment: "production",
      capabilities: ["ai_inference"],
      apiKeyRef: "GROQ_API_KEY",
      available: isAvailable("GROQ_API_KEY"),
    },
    {
      id: "ai-openrouter",
      provider: "ai",
      displayName: `OpenRouter (${(process.env["OPENROUTER_API_KEY"] ?? "").split(",").filter(Boolean).length} keys)`,
      role: "ai-router",
      environment: "production",
      capabilities: ["ai_inference"],
      apiKeyRef: "OPENROUTER_API_KEY",
      available: isAvailable("OPENROUTER_API_KEY"),
    },
    {
      id: "ai-github-models",
      provider: "ai",
      displayName: `GitHub Models (${(process.env["GITHUB_MODELS_API_KEY"] ?? "").split(",").filter(Boolean).length} keys)`,
      role: "ai-inference",
      environment: "production",
      capabilities: ["ai_inference"],
      apiKeyRef: "GITHUB_MODELS_API_KEY",
      available: isAvailable("GITHUB_MODELS_API_KEY"),
    },

    // ── Kaggle ──────────────────────────────────────────
    {
      id: "kaggle-pool",
      provider: "kaggle",
      displayName: `Kaggle 6-Account GPU Pool (${(process.env["KAGGLE_API_TOKENS"] ?? "").split(",").filter(Boolean).length} tokens)`,
      role: "ml-compute",
      environment: "production",
      capabilities: ["health", "metrics"],
      apiKeyRef: "KAGGLE_API_TOKENS",
      available: isAvailable("KAGGLE_API_TOKENS"),
    },

    // ── Notifications ───────────────────────────────────
    {
      id: "notify-telegram",
      provider: "telegram",
      displayName: "Telegram Bot Notifications",
      role: "notifications",
      environment: "production",
      capabilities: ["notify"],
      apiKeyRef: "TELEGRAM_BOT_TOKEN",
      available: isAvailable("TELEGRAM_BOT_TOKEN") && isAvailable("TELEGRAM_CHAT_ID"),
    },
    {
      id: "notify-discord",
      provider: "discord",
      displayName: "Discord Webhook Notifications",
      role: "notifications",
      environment: "production",
      capabilities: ["notify"],
      apiKeyRef: "DISCORD_WEBHOOK_URL",
      available: isAvailable("DISCORD_WEBHOOK_URL"),
    },

    // ── Qdrant ──────────────────────────────────────────
    {
      id: "qdrant-vector",
      provider: "qdrant",
      displayName: "Qdrant Vector DB",
      role: "vector-storage",
      environment: "production",
      capabilities: ["health", "storage"],
      apiKeyRef: "QDRANT_API_KEY",
      url: env.qdrant.url,
      available: isAvailable("QDRANT_URL") && isAvailable("QDRANT_API_KEY"),
    },

    // ── Vercel ──────────────────────────────────────────
    {
      id: "vercel-frontend",
      provider: "vercel",
      displayName: "Vercel Frontend",
      role: "frontend",
      environment: "production",
      capabilities: ["health", "deploy"],
      apiKeyRef: "VERCEL_TOKEN",
      available: isAvailable("VERCEL_TOKEN"),
    },

    // ── Firecrawl ───────────────────────────────────────
    {
      id: "firecrawl-scraper",
      provider: "firecrawl",
      displayName: `Firecrawl (${(process.env["FIRECRAWL_API_KEY"] ?? "").split(",").filter(Boolean).length} keys)`,
      role: "web-scraping",
      environment: "production",
      capabilities: ["health"],
      apiKeyRef: "FIRECRAWL_API_KEY",
      available: isAvailable("FIRECRAWL_API_KEY"),
    },

    // ── Stripe ──────────────────────────────────────────
    {
      id: "stripe-payments",
      provider: "stripe",
      displayName: "Stripe Payments",
      role: "billing",
      environment: "production",
      capabilities: ["health"],
      apiKeyRef: "STRIPE_SECRET_KEY",
      available: isAvailable("STRIPE_SECRET_KEY"),
    },
  ];
}

export type Registry = ReturnType<typeof buildRegistry>;
