#!/usr/bin/env python3
# scripts/generate_registry.py
"""
বাংলা: এই স্ক্রিপ্টটি `docs/Enviorment vs secret key/ENVIRONMENT_AND_API_KEYS_REGISTRY.md`
মাস্টার ম্যাট্রিক্স থেকে সংক্ষেপে ম্যাপ করে `secrets_registry.yaml` generate করে।
টীম এক জায়গায় (_REG) আপডেট করে registry regenerate করে।

প্রতিটা key-এর জন্য `rb:`, `ra:`, `rw:`, `vf:`, `cf:`, `fg:`, `ga:`, `iv:` লেবেল দিয়ে
tier দেওয়া হয় (positional ভুল এড়াতে)।
  C = critical (না থাকলে boot crash -> CI fail)
  I = important (না থাকলে degraded -> CI warning)
  O = optional (না থাকলে ওই feature বন্ধ -> log)

Environment shorthand:
  rb = render-backend | ra = render-admin | rw = render-worker
  vf = vercel-frontend | cf = cloudflare-worker | fg = firebase-gcp
  ga = github-actions | iv = infisical-vault
"""

import os

# (name, "rb:C,ra:C,...", note)
_REG = [
    # ── Core Authentication & Security ──
    ("ENV", "rb:I,ra:I,vf:O,iv:I", "Environment name (production/staging)"),
    ("SUPREMEAI_JWT_SECRET", "rb:C,ra:C,rw:C,iv:C", "JWT secret; <64 bytes হলে RuntimeError (config.py)"),
    ("ENCRYPTION_KEY", "rb:C,ra:C,rw:C,iv:C", "Data/payload encryption key"),
    ("SUPREMEAI_ADMIN_PASSWORD_HASH", "rb:C,ra:C,iv:C", "Hashed admin password (config.py required)"),
    ("SUPREMEAI_ADMIN_TOTP_SECRET", "rb:I,ra:I,iv:I", "Admin 2FA TOTP secret"),
    ("SUPREMEAI_API_KEY", "rb:I,ra:I,iv:I", "Primary API authentication token"),
    ("SUPREMEAI_DOCS_PASSWORD", "ra:I,iv:I", "Admin docs protected password"),
    ("SUPREMEAI_DOCS_USERNAME", "ra:I,iv:I", "Admin docs username"),
    ("ADMIN_AUTHORIZED", "rb:I,ra:I,iv:I", "Admin authorization flag"),
    ("AUTOFIX_AUTHORIZED", "rb:I,ra:I,iv:I", "Auto-fix authorization flag"),

    # ── Database & Storage ──
    ("SUPABASE_URL", "rb:I,ra:I,iv:I", "Supabase API endpoint"),
    ("SUPABASE_KEY", "rb:I,ra:I,iv:I", "Supabase public client key"),
    ("SUPABASE_SECRET_KEY", "rb:O,ra:O,iv:I", "Supabase admin secret key"),
    ("SUPABASE_DATABASE_URL_POOLER", "rb:I,ra:I,rw:I,iv:I", "PostgreSQL PgBouncer URL (worker-এও লাগে)"),
    ("SUPABASE_DATABASE_URL", "rb:I,ra:I,iv:I", "PostgreSQL Database URL"),
    ("SUPABASE_JWKS_URL", "rb:I,ra:I,iv:I", "Supabase JWKS URL"),
    ("SUPABASE_ACCESS_TOKEN", "rb:I,ra:I,iv:I", "Supabase access token"),
    ("SUPABASE_SERVICE_ROLE_KEY", "rb:I,ra:I,iv:I", "Supabase service-role key"),
    ("REDIS_URL", "rb:I,ra:I,rw:I,iv:I", "Upstash/Redis connection string (worker-এও লাগে)"),
    ("UPSTASH_REDIS_REST_URL", "rb:I,ra:I,iv:I", "Upstash REST API URL"),
    ("UPSTASH_REDIS_REST_TOKEN", "rb:I,ra:I,iv:I", "Upstash REST bearer token"),
    ("QDRANT_URL", "rb:I,ra:I,iv:I", "Qdrant vector DB URL"),
    ("QDRANT_API_KEY", "rb:I,ra:I,iv:I", "Qdrant vector DB API key"),
    ("NEO4J_URI", "rb:O,ra:O,iv:I", "Neo4j graph DB URI"),
    ("NEO4J_USER", "rb:O,ra:O,iv:I", "Neo4j username"),
    ("NEO4J_PASSWORD", "rb:O,ra:O,iv:I", "Neo4j password (secret)"),
    ("EXPERIENCE_DB_PATH", "rb:I,ra:I,iv:I", "Experience DB path"),
    ("CHROMADB_PATH", "rb:I,ra:I,iv:I", "ChromaDB path"),

    # ── AI & LLM Services ──
    ("OPENROUTER_API_KEY", "rb:O,ra:O,iv:I", "OpenRouter model hub key"),
    ("DEEPSEEK_API_KEY", "rb:O,ra:O,iv:I", "DeepSeek key"),
    ("GEMINI_API_KEY", "rb:O,ra:O,iv:I", "Google Gemini key"),
    ("GROQ_API_KEY", "rb:O,ra:O,iv:I", "Groq key"),
    ("NVIDIA_API_KEY", "rb:O,ra:O,iv:I", "NVIDIA NIM key"),
    ("OPENAI_API_KEY", "rb:O,ra:O,iv:I", "OpenAI key"),
    ("ANTHROPIC_API_KEY", "rb:O,ra:O,iv:I", "Anthropic Claude key"),
    ("HF_API_KEY", "rb:O,ra:O,iv:I", "HuggingFace key"),
    ("FIRECRAWL_API_KEY", "rb:O,ra:O,iv:I", "Firecrawl scraper key"),
    ("DEVIN_API_KEY", "rb:O,ra:O,iv:I", "Devin agent key"),

    # ── Payment & Billing ──
    ("STRIPE_API_KEY", "rb:I,ra:I,iv:I", "Stripe billing secret key"),
    ("STRIPE_SECRET_KEY", "rb:I,ra:I,iv:I", "Stripe secret key (alias)"),
    ("STRIPE_PUBLISHABLE_KEY", "rb:I,ra:I,vf:I,iv:I", "Stripe public client key"),
    ("STRIPE_WEBHOOK_SECRET", "rb:I,ra:I,iv:I", "Stripe webhook signature secret"),
    ("STRIPE_AGENT_API_KEY", "rb:O,ra:O,iv:I", "Stripe agent API key"),
    ("SENDGRID_API_KEY", "rb:O,ra:O,iv:I", "SendGrid email key"),
    ("SMTP_PASSWORD", "rb:O,ra:O,iv:I", "SMTP password"),
    ("SMTP_USER", "rb:O,ra:O,iv:I", "SMTP user"),

    # ── Communication & Notifications ──
    ("TWILIO_ACCOUNT_SID", "rb:O,ra:O,iv:I", "Twilio account SID"),
    ("TWILIO_AUTH_TOKEN", "rb:O,ra:O,iv:I", "Twilio auth token (secret)"),
    ("DISCORD_WEBHOOK_URL", "rb:O,ra:O,iv:I", "Discord notification webhook"),
    ("DISCORD_BOT_TOKEN", "rb:O,ra:O,iv:I", "Discord bot token"),
    ("DISCORD_OTP_WEBHOOK_URL", "rb:O,ra:O,iv:I", "Discord OTP webhook"),
    ("DISCORD_APP_ID", "rb:O,ra:O,iv:I", "Discord application ID"),
    ("DISCORD_PUBLIC_KEY", "rb:O,ra:O,iv:I", "Discord public key"),
    ("SLACK_WEBHOOK_URL", "rb:O,ra:O,iv:I", "Slack webhook"),
    ("RESEND_API_KEY", "rb:O,ra:O,iv:I", "Resend email key"),
    ("ADMIN_NOTIFICATION_EMAIL", "rb:I,ra:I,iv:I", "Security notification email"),
    ("ADMIN_EMAILS", "rb:I,ra:I,iv:I", "Admin notification emails"),

    # ── Platform Integration & Deployment ──
    ("GITHUB_TOKEN", "rb:O,ra:O,ga:I,iv:I", "GitHub API token (CI)"),
    ("GITHUB_API_TOKEN", "rb:O,ra:O,ga:I,iv:I", "GitHub API token (alt)"),
    ("SUPREMEAI_GITHUB_TOKEN", "rb:O,ra:O,ga:I,iv:I", "GitHub token (extended)"),
    ("GITHUB_CLIENT_ID", "rb:O,ra:O,ga:I,iv:I", "GitHub OAuth client ID"),
    ("GITHUB_CLIENT_SECRET", "rb:O,ra:O,ga:I,iv:I", "GitHub OAuth client secret"),
    ("RENDER_API_KEY", "ga:I,iv:I", "Render API token (CI deploy)"),
    ("RENDER_API_KEY_BACKUP", "ga:I,iv:I", "Render API token (backup)"),
    ("RENDER_DEPLOY_HOOK_URL", "ga:I,iv:I", "Render deploy hook URL"),
    ("RENDER_DEPLOY_HOOK_URL_BACKUP", "ga:I,iv:I", "Render deploy hook (backup)"),
    ("RENDER_PRIMARY_SVC_ID", "ga:I,iv:I", "Render primary service ID"),
    ("RENDER_BACKUP_SVC_ID", "ga:I,iv:I", "Render backup service ID"),
    ("VERCEL_TOKEN", "ga:I,iv:I", "Vercel deploy token"),
    ("VERCEL_PROJECT_ID", "ga:I,iv:I", "Vercel project ID"),
    ("VERCEL_ORG_ID", "ga:I,iv:I", "Vercel org ID"),
    ("VERCEL_OIDC_TOKEN", "ga:I,iv:I", "Vercel OIDC token"),
    ("NETLIFY_AUTH_TOKEN", "ga:I,iv:I", "Netlify auth token"),
    ("NETLIFY_SITE_ID", "ga:I,iv:I", "Netlify site ID"),
    ("CLOUDFLARE_API_TOKEN", "cf:I,iv:I", "Cloudflare zone token"),
    ("CLOUDFLARE_API_KEY", "cf:I,iv:I", "Cloudflare API key"),
    ("CLOUDFLARE_ZONE_ID", "cf:I,iv:I", "Cloudflare zone ID"),
    ("CLOUDFLARE_WORKERS_API_TOKEN", "cf:I,iv:I", "Cloudflare Workers token"),

    # ── Cloud & Infrastructure ──
    ("FIREBASE_SERVICE_ACCOUNT_JSON", "fg:I,iv:I", "Firebase Admin SDK JSON"),
    ("FIRESTORE_PRIVATE_KEY", "rb:O,ra:O,fg:I,iv:I", "Firestore private key"),
    ("FIREBASE_SERVICE_ACCOUNT_PATH", "fg:I", "Firebase service account path"),
    ("GCP_KMS_KEY_RING", "rb:O,ra:O,fg:I,iv:I", "GCP KMS key ring"),
    ("GCP_PROJECT_ID", "rb:O,ra:O,fg:I,iv:I", "GCP project ID"),
    ("GCP_REGION", "rb:O,ra:O,fg:I,iv:I", "GCP region"),
    ("GOOGLE_CLOUD_PROJECT", "rb:O,ra:O,fg:I,iv:I", "Google Cloud project"),
    ("GCP_SA_KEY", "fg:I,ga:I,iv:I", "GCP service account key (CI/Firebase)"),
    ("EVOLUTION_DB_PATH_GCS", "rb:O,ra:O,fg:I,iv:I", "Evolution DB path (GCS)"),
    ("GCP_FIRESTORE_SQLITE_PATH", "rb:O,ra:O,fg:I,iv:I", "Firestore SQLite path"),
    ("BACKUP_BUCKET", "rb:O,ra:O,iv:I", "Backup bucket"),

    # ── Monitoring & Observability ──
    ("SENTRY_DSN", "rb:O,ra:O,iv:I", "Sentry DSN"),
    ("SENTRY_AUTH_TOKEN", "ga:I", "Sentry auth token (CI)"),
    ("LANGSMITH_API_KEY", "rb:O,ra:O,iv:I", "LangSmith tracing key"),
    ("LAUNCHDARKLY_SDK_KEY", "rb:O,ra:O,iv:I", "LaunchDarkly SDK key"),
    ("LAUNCHDARKLY_API_KEY", "rb:O,ra:O,iv:I", "LaunchDarkly API key"),
    ("RUNWAY_API_KEY", "rb:O,ra:O,iv:I", "Runway video key"),
    ("KLING_API_KEY", "rb:O,ra:O,iv:I", "Kling video key"),
    ("RUNPOD_API_KEY", "rb:O,ra:O,iv:I", "RunPod GPU key"),

    # ── Frontend & Client (non-secret public build vars) ──
    ("VITE_API_BASE_URL", "vf:I", "Frontend base backend URL (public)"),
    ("VITE_API_BASE", "vf:I", "Frontend API base URL (public)"),
    ("VITE_SUPABASE_URL", "vf:I", "Client Supabase URL (public)"),
    ("VITE_SUPABASE_ANON_KEY", "vf:I", "Client Supabase anon key (public)"),

    # ── Security & Management ──
    ("CI_WEBHOOK_SECRET", "rb:I,ra:I,ga:I,iv:I", "CI webhook signature secret"),
    ("SERVICE_ROLE", "ra:I", "Admin service role flag"),
    ("DOCS_PASSWORD", "ra:I,iv:I", "Admin docs password"),
    ("INFISICAL_TOKEN", "rb:I,ra:I,rw:I,iv:C", "Infisical project access token (vault boot)"),
    ("INFISICAL_CLIENT_SECRET", "rb:I,ra:I,rw:I,iv:C", "Infisical client secret (vault boot)"),
    ("INFISICAL_CLIENT_ID", "rb:I,ra:I,iv:I", "Infisical client ID"),
    ("INFISICAL_PROJECT_ID", "rb:I,ra:I,iv:I", "Infisical project ID"),
    ("API_KEY_SIGNING_SECRET", "rb:I,ra:I,iv:I", "API key signing secret"),
    ("JIT_OTP_SECRET", "rb:I,ra:I,iv:I", "JIT OTP secret"),

    # ── Boot/test flags (non-secret but required) ──
    ("ALLOW_TEST_AUTH_BYPASS", "rb:I,ra:I,iv:I", "Test auth bypass flag"),
    ("ALLOW_TEST_ORIGIN_BYPASS", "rb:I,ra:I,iv:I", "Test origin bypass flag"),

    # ── CI/tooling-only integrations (scripts/, .github/scripts/ — না চললেও backend চলে) ──
    ("GH_TOKEN", "ga:O", "GitHub API token fallback (detect-previous-failures.py, check_if_fix.py) — GITHUB_TOKEN auto-provided না থাকলে ব্যবহার হয়"),
    ("HF_TOKEN", "ga:O", "HuggingFace access token (model_version_manager.py) — HUGGINGFACE_TOKEN-এর shorthand fallback"),
    ("HUGGINGFACE_TOKEN", "ga:O", "HuggingFace access token (model_version_manager.py)"),
    ("NETLIFY_API_KEY", "ga:O", "Netlify cost-monitoring integration (cost_analyzer.py)"),
    ("PAGERDUTY_ROUTING_KEY", "ga:O", "PagerDuty alert routing (alert_manager.py)"),
    ("SAFETY_API_KEY", "ga:O", "PyUp Safety vulnerability-DB API key (auto_vulnerability_scanner.py)"),
    ("TEST_ADMIN_PASSWORD", "ga:O", "Test-only admin password (create_test_admin.py) — CI/local test fixture, production-এ দরকার নাই"),
]

# বাংলা: যেসব key-এর validity (length) check করা দরকার
_MIN_LENGTH = {
    "SUPREMEAI_JWT_SECRET": 64,
    "ENCRYPTION_KEY": 16,
}


# বাংলা: shorthand -> full environment name mapping
_ENV_FULL = {
    "rb": "render-backend",
    "ra": "render-admin",
    "rw": "render-worker",
    "vf": "vercel-frontend",
    "cf": "cloudflare-worker",
    "fg": "firebase-gcp",
    "ga": "github-actions",
    "iv": "infisical-vault",
}


def _parse_spec(spec: str) -> dict:
    crit = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        env, tier = part.split(":")
        full = _ENV_FULL[env.strip().lower()]
        crit[full] = {"C": "critical", "I": "important", "O": "optional"}[tier.strip().upper()]
    return crit


def generate() -> str:
    lines = []
    lines.append("# SupremeAI 2.0 — Secret/Env Registry (MACHINE-GENERATED from scripts/generate_registry.py)")
    lines.append("# বাংলা: এই ফাইলটি auto-generate করা হয়েছে — হাতে এডিট নয়, generate_registry.py-এর _REG আপডেট করুন।")
    lines.append("# প্রতিটা environment-এর জন্য আলাদা criticality (একই key এক env-এ critical, অন্য env-এ optional)।")
    lines.append("#")
    lines.append("# critical = না থাকলে boot crash -> CI fail")
    lines.append("# important = না থাকলে degraded -> CI warning")
    lines.append("# optional = না থাকলে শুধু feature বন্ধ -> log")
    lines.append("keys:")
    for name, spec, note in _REG:
        crit = _parse_spec(spec)
        lines.append(f"  - name: {name}")
        if name in _MIN_LENGTH:
            lines.append(f"    min_length: {_MIN_LENGTH[name]}")
        crit_str = "{" + ", ".join(f"{env}: {tier}" for env, tier in crit.items()) + "}"
        lines.append(f"    criticality: {crit_str}")
        lines.append(f"    note: \"{note}\"")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "secrets_registry.yaml")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(generate())
    print(f"Wrote {out_path} with {len(_REG)} keys")
