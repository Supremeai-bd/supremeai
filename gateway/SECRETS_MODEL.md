# SECRETS_MODEL — supremeai-api

> **বাংলা:** এই রেপো secrets-নীতি infra রেপোর `SECRETS_MODEL.md` (§৮)-এর সম্প্রসারণ — একই দণ্ড,
> gateway-প্রসারিত প্রয়োগ। Infisical vault-ই একমাত্র secret-উৎস; repo-তে শুধু reference/template।

## নামকরণ-চুক্তি

`<PROVIDER>_<PURPOSE>[_<SLOT>]`

| vault key | কাজ | repo-তে উপস্থিতি |
|---|---|---|
| `GEMINI_API_KEY` | Gemini adapter | শুধু `env-templates/` reference |
| `GROQ_API_KEY` (+`GROQ_API_KEYS` pool) | Groq adapter | শুধু reference |
| `OPENAI_API_KEY` | ভবিষ্যৎ adapter (P4) | শুধু reference |
| `SUPREMEAI_API_KEY_HASHES` | client-key যাচাই (sha256 তালিকা) | শুধু reference |

## লৌহদণ্ড

1. **Provider credential client-কে কখনো ফেরত যায় না** — `SUPREMEAI_API_KEY` হলো gateway-র
   প্রবেশ-পত্র, provider-key-র কপি নয় (plan §১০)
2. Client-key plaintext কোথাও নয় (env/log/git-এ নয়) — শুধু sha256-hash vault-এ
3. নিষিদ্ধ ঘোষণা: "শুধু একবার", "শুধু debugging", "placeholder মনে হচ্ছে" — কোনো ব্যতিক্রম নেই
4. Rotation = vault-এ মান বদল + পরিষেবা রিস্টার্ট; git-history কখনো প্রমাণ-স্থল নয়
5. দুর্ঘটনায় secret ঢুকলে: তাৎক্ষণিক vault-rotation → history-purge পরে — ক্রম এটাই

## Gateway free API route approval

`SUPREMEAI_FREE_ROUTE_POLICY` is a Vault-managed JSON list. It is separate from
client-key verification (`SUPREMEAI_API_KEY_HASHES`) and any quota estimates.
Keep both the approvals and the provider credentials out of chat, code, and CI
artifacts. This example is illustrative and not a usable approval:

```json
[
  {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "key_sha256": "<lowercase SHA-256 of the exact configured provider key>",
    "models": ["publisher/model:free"],
    "vision_models": [],
    "expires_at": "2026-12-01T00:00:00Z"
  }
]
```

- Use the exact configured HTTPS API base (a trailing slash is ignored). Bind it
  to the credential in the configured slot, a concrete model list in priority
  order, and an expiry with timezone. An optional `vision_models` list must be a
  subset of `models`; include only models with verified free image entitlement.
- Before approval, verify the account, free-only billing controls and quota,
  endpoint, modalities and requested options. An approval does not change the
  provider's billing policy. For OpenRouter and Kilo the Gateway also requires
  fresh `/models` evidence fetched with the same credential and concrete
  `:free` slugs, including explicit zero prompt, completion and all other
  listed charges. A meta-router or missing prices are not evidence.
- Missing, invalid, expired, or mismatched approvals disable that API route.
  Rotate/remove the approval together with the credential and restart the
  Gateway; live entitlement and rotation must be checked in staging. The
  webhook relay has separate access, cost, and data-handling requirements.
- Inbound Telegram strategy processing requires both `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_WEBHOOK_SECRET`, with the same secret registered at Telegram. Do not
  configure either until the approved caller and data flow are confirmed.

See the [manual rollout checklist](../docs/operations/manual-rollout-checklist.md)
for operational evidence and production approval.

## CI প্রয়োগ

`.github/workflows/secret-scan.yml` — ১৩-প্যাটার্ন fail-closed স্ক্যান; `env-templates/`-এর
`__VAULT:...__` reference-গুলো প্যাটার্নের বাইরে (placeholder-এ প্রকৃত মান অসম্ভব)।
