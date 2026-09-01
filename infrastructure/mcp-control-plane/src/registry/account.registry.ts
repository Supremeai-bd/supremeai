import { env } from "../lib/env.js";
import { ProviderName } from "./provider.registry.js";
import { Capability } from "./capability.registry.js";

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
export function buildAccountRegistry(): ProviderAccount[] {
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
      url: env.render.primary.url,
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
      url: env.render.worker.url,
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
      url: env.render.scraper.url,
      serviceId: env.render.scraper.serviceId,
      available: isAvailable("RENDER_API_KEY_3"),
    },
    {
      id: "render-mcp",
      provider: "render",
      displayName: "Render MCP (Control Tower)",
      role: "mcp-control",
      environment: "production",
      capabilities: ["health", "logs", "deploy", "restart", "env_vars"],
      apiKeyRef: "RENDER_API_KEY_4",
      url: env.render.controlTower.url,
      serviceId: env.render.controlTower.serviceId,
      available: isAvailable("RENDER_API_KEY_4"),
    },

    // ── GitHub ──────────────────────────────────────────
    {
      id: "github-primary",
      provider: "github",
      displayName: "GitHub Repo (SaifulHaqueNiloy/supremeai)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GH_TOKEN",
      available: isAvailable("GH_TOKEN") || isAvailable("GITHUB_TOKEN"),
    },

    // ── Supabase ──────────────────────────────────────────
    {
      id: "supabase-primary",
      provider: "supabase",
      displayName: "Supabase Primary (Postgres + Auth)",
      role: "primary-db",
      environment: "production",
      capabilities: ["health", "metrics"],
      apiKeyRef: "SUPABASE_SERVICE_ROLE_KEY",
      url: env.supabase.url,
      available: isAvailable("SUPABASE_SERVICE_ROLE_KEY"),
    },

    // ── Redis (Upstash) ───────────────────────────────────
    {
      id: "redis-primary",
      provider: "redis",
      displayName: "Upstash Redis (Cache + Queue)",
      role: "cache",
      environment: "production",
      capabilities: ["health", "metrics", "storage"],
      apiKeyRef: "UPSTASH_REDIS_REST_TOKEN",
      url: env.redis.url,
      available: isAvailable("UPSTASH_REDIS_REST_TOKEN"),
    },

    // ── Cloudflare ────────────────────────────────────────
    {
      id: "cloudflare-primary",
      provider: "cloudflare",
      displayName: "Cloudflare (DNS + Workers + Analytics)",
      role: "edge",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_API_TOKEN",
      available: isAvailable("CLOUDFLARE_API_TOKEN"),
    },

    // ── Infisical ─────────────────────────────────────────
    {
      id: "infisical-primary",
      provider: "infisical",
      displayName: "Infisical (Secrets Manager)",
      role: "secrets",
      environment: "production",
      capabilities: ["health", "secrets"],
      apiKeyRef: "INFISICAL_CLIENT_SECRET",
      available: isAvailable("INFISICAL_CLIENT_SECRET"),
    },

    // ── Firebase ──────────────────────────────────────────
    {
      id: "firebase-primary",
      provider: "firebase",
      displayName: "Firebase (Auth + Storage)",
      role: "auth-storage",
      environment: "production",
      capabilities: ["health", "auth", "storage"],
      apiKeyRef: "FIREBASE_SERVICE_ACCOUNT_JSON",
      available: isAvailable("FIREBASE_SERVICE_ACCOUNT_JSON"),
    },

    // ── AI Providers (Multi-Key Pools) ────────────────────
    {
      id: "ai-openai",
      provider: "ai",
      displayName: "OpenAI API Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "OPENAI_API_KEYS",
      available: isAvailable("OPENAI_API_KEYS"),
    },
    {
      id: "ai-gemini",
      provider: "ai",
      displayName: "Google Gemini API Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "GEMINI_API_KEYS",
      available: isAvailable("GEMINI_API_KEYS"),
    },
    {
      id: "ai-anthropic",
      provider: "ai",
      displayName: "Anthropic Claude API Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "ANTHROPIC_API_KEYS",
      available: isAvailable("ANTHROPIC_API_KEYS"),
    },
    {
      id: "ai-deepseek",
      provider: "ai",
      displayName: "DeepSeek API Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "DEEPSEEK_API_KEYS",
      available: isAvailable("DEEPSEEK_API_KEYS"),
    },

    // ── Kaggle ────────────────────────────────────────────
    {
      id: "kaggle-pool",
      provider: "kaggle",
      displayName: "Kaggle Accounts Pool (6 keys)",
      role: "data-science",
      environment: "production",
      capabilities: ["health", "storage"],
      apiKeyRef: "KAGGLE_API_TOKENS",
      available: isAvailable("KAGGLE_API_TOKENS"),
    },

    // ── Notifications ─────────────────────────────────────
    {
      id: "telegram-primary",
      provider: "telegram",
      displayName: "Telegram Alerts Bot",
      role: "alerts",
      environment: "production",
      capabilities: ["health", "notify"],
      apiKeyRef: "TELEGRAM_BOT_TOKEN",
      available: isAvailable("TELEGRAM_BOT_TOKEN"),
    },
    {
      id: "discord-primary",
      provider: "discord",
      displayName: "Discord Webhook",
      role: "alerts",
      environment: "production",
      capabilities: ["health", "notify"],
      apiKeyRef: "DISCORD_WEBHOOK_URL",
      available: isAvailable("DISCORD_WEBHOOK_URL"),
    },
  ];
}
