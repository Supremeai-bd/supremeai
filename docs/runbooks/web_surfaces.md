# Web Surfaces Operations Runbook (H4)

## Overview
Web-engine surfaces (`duck`, `gemini-web`) are **fallback-only** lanes routed through the browser relay (`browser/server.py`) and governed by `config/web_surfaces.yaml` (SSOT).

## 1. Re-minting Web-Slot Approvals (Every 6 Hours)
Pre-existing web-slot approvals are dropped without evidence. Re-mint approvals at least every 6 hours:

```bash
python3 scripts/ops/free_route_policy_tool.py \
  --provider claude_web --provider chatgpt_web \
  --base-url https://<relay> \
  --from-relay \
  --credential-env STEALTH_WEBHOOK_URL \
  --models duck-claude,duck-gpt \
  --merge --ttl-hours 24
```

## 2. Emergency Kill Switch (S3)
To disable an engine immediately without redeploying:

```bash
curl -X POST https://<relay>/admin/engines \
  -H "X-Stealth-Secret: $STEALTH_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"engine": "gemini-web", "disabled": true, "reason": "cookie burn"}'
```

To re-enable:
```bash
curl -X POST https://<relay>/admin/engines \
  -H "X-Stealth-Secret: $STEALTH_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"engine": "gemini-web", "disabled": false}'
```

For persistent disable across restarts, set:
`SUPREMEAI_RELAY_DISABLED_ENGINES="gemini-web:cookie burn"`

## 3. Injury Hysteresis & Probation (S5)
- Consecutive injuries double the slot cooldown (`1x, 2x, 4x, 8x`).
- Session injuries are capped at `ENGINE_REFRESH_S` (30 min) so renewed cookies are re-probed.
- A recovering slot is ranked strictly behind clean slots until a real success clears `injury_level`.
