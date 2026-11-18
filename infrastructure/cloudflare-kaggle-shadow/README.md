# SupremeAI Kaggle 24/7 Shadow Node (Cloudflare Worker)

This Cloudflare Worker automates 24/7 rotation across up to 6 Kaggle accounts using Kaggle's REST API and acts as a permanent reverse-proxy URL for the active `trycloudflare.com` tunnel.

## Setup & Deployment

1. **Create the KV Namespace:**
   ```bash
   cd infrastructure/cloudflare-kaggle-shadow
   npx wrangler kv namespace create SHADOW_STATE
   ```
   Copy the generated `id` into `wrangler.toml` replacing `REPLACE_WITH_KV_NAMESPACE_ID`.

2. **Configure Secrets:**
   - `KAGGLE_ACCOUNTS_JSON`: A JSON array of your 6 Kaggle accounts:
     ```json
     [
       {"username": "user1", "key": "kaggle_api_key_1"},
       {"username": "user2", "key": "kaggle_api_key_2"}
     ]
     ```
     ```bash
     npx wrangler secret put KAGGLE_ACCOUNTS_JSON
     ```
   - `SHADOW_REGISTER_SECRET`: Any strong random string (used by the Kaggle notebook to register its tunnel URL).
     ```bash
     npx wrangler secret put SHADOW_REGISTER_SECRET
     ```
   - `WORKER_PUBLIC_URL`: Your deployed worker URL (e.g. `https://supremeai-kaggle-shadow.<subdomain>.workers.dev`) so the cron trigger knows where the notebook should register.
     ```bash
     npx wrangler secret put WORKER_PUBLIC_URL
     ```

3. **Deploy:**
   ```bash
   npx wrangler deploy
   ```

4. **Bootstrap the First Node:**
   ```bash
   curl -X POST https://supremeai-kaggle-shadow.<subdomain>.workers.dev/rotate \
     -H "Authorization: Bearer <YOUR_SHADOW_REGISTER_SECRET>"
   ```

5. **Verify:**
   - Check active node status: `GET /status`
   - Check proxied health: `GET /health/live`
