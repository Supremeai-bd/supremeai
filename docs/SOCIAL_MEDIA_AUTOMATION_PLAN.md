# Social Media Automation Feature — Plan & Readiness Analysis

> Feature: SupremeAI (and any user) connects social accounts (FB, IG, X/Twitter, LinkedIn, TikTok, YouTube, …) and auto-publishes approved content at fixed times. Primary first use-case: SupremeAI's own marketing/page maintenance.

## 1. Vision

- **SupremeAI-owned marketing**: a content calendar + brand voice; SupremeAI generates, schedules, and publishes posts (and maintains pages) on its own social accounts without manual intervention, with human approval gate.
- **User-facing (multi-tenant)**: any user connects their own accounts and gets the same scheduling/publishing capability, tenant-isolated, approval-first.
- **Principle**: approval-first, no silent success, fail-closed on missing credentials, honest status. Mirrors existing `SocialGrowthCircle` design.

## 2. Readiness inventory (what already exists)

### Backend — built & wired
| Component | Location | Status |
|---|---|---|
| `SocialGrowthCircle` (drafts, approve, pause/resume, tenant scoping, audit) | `core/social_growth.py` | ✅ Built, durable (Redis mirror), hydrated at boot |
| API route `/api/v1/social/*` (drafts CRUD, approve, pause, resume) | `core/api/routes/social_growth.py` → `gateway/routes/social_growth.py` | ✅ Wired |
| Auth/tenant identity | `api.deps.get_current_user_token` | ✅ |
| Tests (approval, tenant scoping, pause) | `core/tests/core/test_social_growth.py` | ✅ 3 tests |
| Scheduled Tasks (S11) — CRUD, once/daily/weekly/custom cron, execution history | `core/api/routes/scheduled_tasks.py` | ✅ |
| Due-task sweep executor (CAS claim, run fabric, LLM prompt execution) | `core/scheduled_task_sweep.py` | ✅ Wired, default-on agent |
| Browser automation (Playwright, stealth profiles, session/cookie bridge) | `core/tools/browser/*`, `core/browser/*` | ✅ Available (publish fallback) |
| Integrations framework (Integration model, OAuth state signing, vault listing) | `core/api/routes/integrations.py` | ✅ GitHub implemented; pattern reusable |
| Email agent (IMAP real, Gmail OAuth not implemented) | `core/tools/social/email_agent.py` | ⚠️ Partial |
| Telegram bot (full) | `core/tools/social/telegram_bot/*` | ✅ |
| Viral referral (social share deep links) | `core/tools/social/viral_referral_engine.py` | ✅ |
| Content generation (LLM gateway, prompt templates, chat) | `core/llm/*` | ✅ |
| Durable state store (Redis mirror + in-process) | `core/state_store.py` | ✅ |
| Multi-tenant RLS / Supabase | `database/*` | ✅ |

### Frontend / UI
| Component | Status |
|---|---|
| Studio pages for social growth (connect accounts, calendar, draft editor, approval queue, analytics) | ❌ None (no `.tsx` references found) |
| i18n (bn/en) for social flows | ❌ None |

### Platform coverage (SocialPlatform enum)
- ✅ Facebook, Instagram
- ❌ Twitter/X, LinkedIn, TikTok, YouTube, Threads, Pinterest

## 3. Gap analysis (what is missing)

### A. Platform connection layer (OAuth / tokens)
- No OAuth flows for any social platform (only GitHub exists).
- No `SocialAccount` model: platform, account_id, handle, encrypted access/refresh tokens, scopes, expiry, status.
- No token refresh scheduler / expiry monitoring.
- Free-tier constraint: prefer official free tiers (FB/IG Graph API, LinkedIn API, YouTube Data API, X API v2 limited); paid tiers only later.

### B. Publishing engine
- `approve()` returns `requires_browser_publish: True` but **no consumer publishes** anything.
- No publisher abstraction per platform.
- No scheduled publish sweep: approved drafts with `scheduled_for <= now` are never published.
- No status transitions `APPROVED → PUBLISHING → PUBLISHED/FAILED`, no retry/backoff.
- No idempotency (platform post id) to avoid duplicate posts on crash.
- Custom cron (`schedule_type=custom`) is explicitly unsupported in the sweep (returns `None`); social posts needing custom cadence won't run.

### C. Content & calendar
- No content templates / brand-voice profiles.
- No AI generation endpoint dedicated to social posts (reuse LLM gateway but wire it).
- No media upload pipeline (media_urls stored but never uploaded to platforms).
- No recurrence rule beyond daily/weekly (no cron, no "every N days", no time-of-day windows).

### D. Safety, moderation, analytics
- No content moderation / brand-safety check before publish.
- No per-platform rate limiting / quota handling.
- Analytics: no fetch of post metrics (reach, likes, comments).
- Audit log exists (list) but not persisted/queried as a timeline.

### E. Frontend
- No UI at all for the social growth feature.

### F. SupremeAI's own marketing operations
- No defined content pillars, cadence, brand voice prompt.
- No seed calendar.

## 4. Architecture design

```
┌─────────────────────────────────────────────────────────────┐
│  Studio UI (connect accounts, calendar, editor, queue, KPI)  │
└──────────────┬──────────────────────────────────────────────┘
               │ REST (JWT tenant)
┌──────────────▼──────────────────────────────────────────────┐
│  Gateway routes: /api/v1/social/* , /api/v1/integrations/*  │
│  (OAuth start/callback, account list, revoke)               │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  Core domain                                                │
│  • SocialGrowthCircle  (drafts, approve, pause)  [exists]   │
│  • SocialAccountStore  (connected accounts, tokens) [new]    │
│  • ContentCalendar     (scheduled_for, recurrence) [new]     │
│  • PublisherRegistry   (per-platform adapters) [new]         │
│  • SocialPublishSweep  (CAS claim + publish + retry) [new]   │
│  • ContentModeration   (LLM safety gate) [new]               │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  Platform adapters                                          │
│  • FacebookAdapter (Graph API)        • InstagramAdapter     │
│  • XAdapter (API v2)                  • LinkedInAdapter      │
│  • TikTokAdapter                      • YouTubeAdapter       │
│  • BrowserPublishAdapter (stealth fallback, cookie bridge)   │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────┐
│  Storage: Supabase (accounts, drafts, posts, metrics)        │
│  + Redis durable state (drafts/pause) [exists]              │
│  + MinIO (media)                                            │
└─────────────────────────────────────────────────────────────┘
```

**Publishing strategy (hybrid):**
1. Prefer official APIs (free tiers) — reliable, no anti-bot risk.
2. Browser-automation fallback (stealth Playwright + cookie bridge) for platforms without a free API or pending app review — uses the user's own logged-in session, higher fragility.
3. Never store passwords; only OAuth tokens in the encrypted vault (SecureCredentialStore pattern).

## 5. Phased implementation plan

### Phase 0 — Decisions & secrets (≈1 week)
- Decide official-API vs browser-fallback per platform (matrix).
- Register developer apps (FB/IG Graph, X, LinkedIn, TikTok, YouTube), scopes.
- Store client secrets in Infisical/secret vault.
- Define `SocialAccount` schema + migration.
- **Deliverable**: decision doc + secrets in vault + schema migration.

### Phase 1 — Platform connection layer (≈2–3 weeks)
- `SocialAccount` model + CRUD service.
- OAuth start/callback routes per platform (reuse `_sign_oauth_state` pattern).
- Token refresh scheduler (background agent, env-gated).
- Account listing/revoke endpoints.
- Tests: OAuth state, token storage, refresh.
- **Deliverable**: user can connect/disconnect FB, IG, X, LinkedIn.

### Phase 2 — Content & calendar (≈2 weeks)
- Extend `SocialPlatform` enum to all target platforms.
- Content templates + brand-voice profile (per tenant + SupremeAI default).
- AI generation endpoint for social posts (LLM gateway).
- Media upload pipeline (MinIO → platform media).
- Recurrence rules (daily/weekly/custom cron) — fix custom-cron support (reuse cron parser or restrict to daily/weekly honestly).
- **Deliverable**: create/schedule drafts for all platforms with media.

### Phase 3 — Publishing engine (≈2–3 weeks)
- `Publisher` interface + per-platform adapters.
- `SocialPublishSweep` agent (CAS claim pattern from `scheduled_task_sweep.py`).
- Status transitions + retry with exponential backoff + dead-letter.
- Idempotency via platform post id.
- Browser-publish fallback adapter (stealth + cookie bridge).
- Wire `approve()` → schedule → sweep publishes.
- **Deliverable**: approved drafts auto-publish at `scheduled_for`.

### Phase 4 — Safety, moderation, analytics (≈1–2 weeks)
- LLM content-moderation gate before publish (brand safety, prohibited terms).
- Per-platform rate limiting / quota.
- Analytics fetcher (periodic) + storage + dashboard data.
- Audit timeline endpoint.
- **Deliverable**: safe, observable publishing.

### Phase 5 — Frontend (≈2–3 weeks)
- Studio pages: Connect Accounts, Content Calendar, Draft Editor, Approval Queue, Analytics.
- i18n (bn/en).
- **Deliverable**: end-to-end user journey.

### Phase 6 — SupremeAI own marketing (ongoing)
- Define content pillars, cadence, brand voice prompt.
- Seed 30-day calendar.
- Monitor metrics, iterate weekly.

## 6. Risks & constraints

- **Free-tier constraint** (project policy): all keys free; social APIs must use free tiers only; paid usage only when paid keys arrive.
- **Anti-bot / ToS**: browser-publish fallback risks account bans; official APIs preferred; clear user consent; rate limits.
- **Security**: tokens encrypted at rest (SecureCredentialStore); never log secrets; per-tenant isolation; RLS.
- **Reliability**: idempotency + retry + dead-letter to avoid duplicate/lost posts.
- **Honesty doctrine**: never claim a post published unless platform confirms; surface failures in audit + status.
- **Custom cron unsupported today**: either implement a cron parser or restrict recurrence honestly (no fake "supported").

## 7. Effort summary

| Scope | Estimate |
|---|---|
| MVP (FB + IG publish + scheduling, API-only) | 4–5 weeks |
| Full multi-platform + browser fallback | 10–12 weeks |
| + Frontend + analytics | 13–15 weeks |
| SupremeAI own marketing ops | ongoing |

## 8. Immediate next steps (if approved)

1. Confirm platform priority (recommend: FB + IG first, then X, then LinkedIn).
2. Register developer apps + store secrets.
3. Create `SocialAccount` model + migration (Phase 1 start).
4. Add `SocialPlatform` values for X, LinkedIn, TikTok, YouTube (Phase 2 prep).
5. Implement `SocialPublishSweep` skeleton reusing `scheduled_task_sweep.py` CAS pattern.
6. Add frontend route stubs in Studio (Phase 5 prep).

---
*Generated from deep analysis of repository state (2026-11-15).*
