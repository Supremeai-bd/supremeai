export type ServiceCircle = "ai" | "infrastructure" | "data" | "security" | "integration";

export type ServiceState = "registered" | "configured" | "reachable" | "authorized" | "healthy";

export interface ServiceDescriptor {
  provider: string;
  circle: ServiceCircle;
  requiredEnv: string[];
  states: ServiceState[];
}

export const serviceDescriptors: ServiceDescriptor[] = [
  { provider: "gemini", circle: "ai", requiredEnv: ["GEMINI_API_KEY"], states: ["registered"] },
  { provider: "groq", circle: "ai", requiredEnv: ["GROQ_API_KEY"], states: ["registered"] },
  { provider: "openrouter", circle: "ai", requiredEnv: ["OPENROUTER_API_KEY"], states: ["registered"] },
  { provider: "render", circle: "infrastructure", requiredEnv: ["RENDER_API_KEY"], states: ["registered"] },
  { provider: "cloudflare", circle: "infrastructure", requiredEnv: ["CLOUDFLARE_API_TOKEN"], states: ["registered"] },
  { provider: "redis", circle: "infrastructure", requiredEnv: ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"], states: ["registered"] },
  { provider: "supabase", circle: "data", requiredEnv: ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"], states: ["registered"] },
  { provider: "qdrant", circle: "data", requiredEnv: ["QDRANT_URL"], states: ["registered"] },
  { provider: "infisical", circle: "security", requiredEnv: ["INFISICAL_PROJECT_ID"], states: ["registered"] },
  { provider: "firebase", circle: "security", requiredEnv: ["FIREBASE_SERVICE_ACCOUNT_JSON"], states: ["registered"] },
  { provider: "github", circle: "integration", requiredEnv: ["GITHUB_TOKEN"], states: ["registered"] },
  { provider: "telegram", circle: "integration", requiredEnv: ["TELEGRAM_BOT_TOKEN"], states: ["registered"] },
  { provider: "discord", circle: "integration", requiredEnv: ["DISCORD_WEBHOOK_URL"], states: ["registered"] },
  { provider: "stripe", circle: "integration", requiredEnv: ["STRIPE_SECRET_KEY"], states: ["registered"] },
];

export function getServiceDescriptors() {
  return serviceDescriptors.map((service) => ({
    ...service,
    configured: service.requiredEnv.every((name) => Boolean(process.env[name])),
  }));
}
