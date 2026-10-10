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
  /** Optional: explicit health-check path appended to `url` (system.health).
   *  When absent, the probe tries /health then /api/v1/health. Providers with
   *  non-HTTP health semantics (github/supabase/redis) get dedicated probes. */
  healthPath?: string;
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
      healthPath: "/api/v1/health", // FastAPI core API
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
      healthPath: "/health",
      available: isAvailable("RENDER_API_KEY_2"),
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
      healthPath: "/health",
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
      healthPath: "/health", // control tower's own health endpoint
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
      url: "https://api.github.com/repos/SaifulHaqueNiloy/supremeai",
      available: isAvailable("GH_TOKEN") || isAvailable("GITHUB_TOKEN"),
    },
    {
      id: "github-test-ground",
      provider: "github",
      displayName: "supremeai test ground",
      role: "source-control",
      environment: "development",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GH_TOKEN",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai",
      available: isAvailable("GH_TOKEN") || isAvailable("GITHUB_TOKEN") || isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE"),
    },

    // ── GitHub — paykaribazaronline supremeai-federation (সম্পূর্ণ-কভারেজ, Task 35) ──
    // বাংলা: paykaribazaronline অ্যাকাউন্টের প্রতিটি supremeai-সংশ্লিষ্ট রিপো টাওয়ারে
    // যুক্ত। কী আসে Infisical vault থেকে (GITHUB_PAT_PAYKARIBAZARONLINE — বুট-সময়ে
    // pullSecretsIntoProcessEnv() process.env-এ ভরে; মান কোডে/কমিটে কখনো নেই)।
    // প্রতিটি entry = টাওয়ারের github.* টুলে আলাদা accountId → প্রতি-রিপো
    // workflow-run / secret / PR / ফাইল পর্যবেক্ষণ।
    {
      id: "github-pay-supremeai",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-api",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-api)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-api",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-archive",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-archive)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-archive",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-core",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-core)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-core",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-infrastructure",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-infrastructure)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-infrastructure",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-mcp-control-plane",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-mcp-control-plane)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-mcp-control-plane",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-open",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-open)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-open",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-sdk",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-sdk)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-sdk",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
    },
    {
      id: "github-pay-supremeai-studio",
      provider: "github",
      displayName: "GitHub Repo (paykaribazaronline/supremeai-studio)",
      role: "source-control",
      environment: "production",
      capabilities: ["health", "logs", "metrics"],
      apiKeyRef: "GITHUB_PAT_PAYKARIBAZARONLINE",
      url: "https://api.github.com/repos/paykaribazaronline/supremeai-studio",
      available: isAvailable("GITHUB_PAT_PAYKARIBAZARONLINE") || isAvailable("GITHUB_TOKEN") || isAvailable("GH_TOKEN"),
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
      // Prefer the Upstash REST URL (https, port 443) — the raw REDIS_URL uses
      // the TCP-only port 6379 which every REST probe would fail on.
      url: env.redis.restUrl || env.redis.url,
      available: isAvailable("UPSTASH_REDIS_REST_TOKEN"),
    },

    // ── Cloudflare (5-Account Federation Pool) ────────────
    {
      id: "cloudflare-primary",
      provider: "cloudflare",
      displayName: "Cloudflare Primary (DNS + Workers + Edge)",
      role: "edge",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_API_TOKEN",
      available: isAvailable("CLOUDFLARE_API_TOKEN") || isAvailable("CLOUDFLARE_GLOBAL_API_KEY"),
    },
    {
      id: "cloudflare-secondary",
      provider: "cloudflare",
      displayName: "Cloudflare Secondary (Edge Failover)",
      role: "edge-secondary",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_SECONDARY_GLOBAL_API_KEY",
      available: isAvailable("CLOUDFLARE_SECONDARY_GLOBAL_API_KEY"),
    },
    {
      id: "cloudflare-tertiary",
      provider: "cloudflare",
      displayName: "Cloudflare Tertiary (Edge Failover)",
      role: "edge-tertiary",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_TERTIARY_GLOBAL_API_KEY",
      available: isAvailable("CLOUDFLARE_TERTIARY_GLOBAL_API_KEY"),
    },
    {
      id: "cloudflare-quaternary",
      provider: "cloudflare",
      displayName: "Cloudflare Quaternary (Edge Failover)",
      role: "edge-quaternary",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_QUATERNARY_GLOBAL_API_KEY",
      available: isAvailable("CLOUDFLARE_QUATERNARY_GLOBAL_API_KEY"),
    },
    {
      id: "cloudflare-quinary",
      provider: "cloudflare",
      displayName: "Cloudflare Quinary (Edge Failover)",
      role: "edge-quinary",
      environment: "production",
      capabilities: ["health", "metrics", "logs"],
      apiKeyRef: "CLOUDFLARE_QUINARY_GLOBAL_API_KEY",
      available: isAvailable("CLOUDFLARE_QUINARY_GLOBAL_API_KEY"),
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
      id: "ai-gemini",
      provider: "ai",
      displayName: "Google Gemini API Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "GEMINI_API_KEY",
      available: env.ai.geminiKeys.length > 0,
    },
    {
      id: "ai-groq",
      provider: "ai",
      displayName: "Groq LPU Inference Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "GROQ_API_KEY",
      available: env.ai.groqKeys.length > 0,
    },
    {
      id: "ai-openrouter",
      provider: "ai",
      displayName: "OpenRouter Unified Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "OPENROUTER_API_KEY",
      available: env.ai.openrouterKeys.length > 0,
    },
    {
      id: "ai-mistral",
      provider: "ai",
      displayName: "Mistral AI Pool",
      role: "llm-inference",
      environment: "production",
      capabilities: ["health", "ai_inference", "metrics"],
      apiKeyRef: "MISTRAL_API_KEY",
      available: !!env.ai.mistralKey,
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
      available: env.kaggle.tokens.length > 0,
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
