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

## CI প্রয়োগ

`.github/workflows/secret-scan.yml` — ১৩-প্যাটার্ন fail-closed স্ক্যান; `env-templates/`-এর
`__VAULT:...__` reference-গুলো প্যাটার্নের বাইরে (placeholder-এ প্রকৃত মান অসম্ভব)।
