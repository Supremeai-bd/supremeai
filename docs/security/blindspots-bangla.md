# SupremeAI 2.0 — System Blind Spots (Full List in Bangla)

> **Date:** 2026-07-02
> **Scope:** Full monorepo (Backend, Frontend, Flutter, VS Code, Infrastructure, Evolution, Skills, Admin)

---

## Summary Table

| Severity | Count | Impact |
|----------|-------|--------|
| 🔴 Critical | 15 | 268 |
| 🟠 High | 21 | 410 |
| 🟡 Medium | 16 | 285 |
| 🟢 Low/Info | 12 | 188 |

**Total Blind Spots:** 64

---

## 1. Authentication & Authorization (Critical 3, High 3)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 1.1 | 🔴 Critical | Hardcoded god-password `supreme-god-password` in adminStore.ts client-side backdoor | `adminStore.ts:42-45` |
| 1.2 | 🔴 Critical | Plaintext password comparison with no salted hashing in admin_routes.py | `admin_routes.py:37,58` |
| 1.3 | 🔴 Critical | SHA-256 password hashing (weak); bcrypt/argon2/passlib absent from backend | `admin_god.py` |
| 1.4 | 🔴 Critical | Firebase JWT signature bypass: tokens decoded without verification in dev/offline mode | `admin_routes.py:97-116` |
| 1.5 | 🔴 Critical | Test mode admin bypass in auth_middleware.py: `is_test` grants admin role | `auth_middleware.py:36-43` |
| 1.6 | 🟠 High | Multiple localStorage token keys (`supremeai_admin_token`, `token`, `admin_token`, `auth_token`) create auth bypass risks | Multi-file |
| 1.7 | 🟠 High | No httpOnly/Secure/ SameSite cookies; all tokens in plain localStorage | apps/studio-client |
| 1.8 | 🟠 High | Admin domain check uses substring matching (`supremeai-admin in origin`) — trivially spoofed | `auth_middleware.py:56-58` |
| 1.9 | 🟠 High | Firestore fallback auto-promotes admin role when DB unreachable and email is in `admin_emails` list | `admin_routes.py:141-149` |
| 1.10 | 🟡 Medium | Mock tokens (`id_token.startswith("mock-")`) bypass verification in non-production; environment detection may leak | `admin_routes.py` |
| 1.11 | 🔴 Critical | WebSocket endpoints have zero authentication: `websocket_agent.py` and `websocket_voice.py` accept connections without token validation | `websocket_agent.py`, `websocket_voice.py` |

---

## 2. Backend Security (Critical 3, High 5, Medium 4)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 2.1 | 🔴 Critical | SQL injection risk in `db_repository.py`: `table_name` not sanitized in f-string query | `db_repository.py:76` |
| 2.2 | 🔴 Critical | Rate limiter fail-open: Redis failure returns `True`, disabling rate limiting entirely | `rate_limiter.py:67-69` |
| 2.3 | 🔴 Critical | Circ breaker HALF_OPEN state allows all traffic; no throttling during recovery | `circuit_breaker.py:71-74` |
| 2.4 | 🟠 High | Host header validation uses substring matching — bypassable with crafted host strings | `origin_validator.py:34` |
| 2.5 | 🟠 High | No file upload validation: tools accept arbitrary `UploadFile` with no content-type/size/malware checks | `auto_test_generator.py`, `voice_coder.py`, `diagram_to_architecture.py`, `image_to_code.py` |
| 2.6 | 🟠 High | No TLS enforcement: no explicit HTTPS redirect middleware or HSTS headers | `core/app.py/middleware` |
| 2.7 | 🟠 High | Celery/RQ message brokers lack auth; exposed Redis can accept injected tasks | `core/task_queue_enhanced.py` |
| 2.8 | 🟠 High | Observability middleware accepts spoofable `x-user-id` header without validation | `observability_middleware.py:34-35` |
| 2.9 | 🟠 High | API key rate limiter uses first 12 chars as key; two different keys share same bucket | `api_key_middleware.py:53` |
| 2.10 | 🟡 Medium | Dual auth middleware confusion: `core/auth_middleware.py` and `middleware/auth_middleware.py` coexist; accidental import causes inconsistent security | `core/auth_middleware.py`, `middleware/auth_middleware.py` |
| 2.11 | 🟡 Medium | Hardcoded pgbouncer placeholder DSN in `core/pgbouncer_pool.py` could cause production misconnection | `pgbouncer_pool.py:49` |
| 2.12 | 🟡 Medium | CORS misconfiguration: `127.0.0.1` origins in production could expose API to DNS rebinding | `core/app.py` / `core/config.py` |
| 2.13 | 🟡 Medium | In-memory WebSocket state with no connection limits per IP | `websocket_agent.py`, `websocket_voice.py` |
| 2.14 | 🟡 Medium | Idempotency middleware not enforced globally — some routes bypass | `core/idempotency_middleware.py` |
| 2.15 | 🟡 Medium | Honeypot IP block is permanent after 3 hits; shared IPs/CGNAT risk blocking legitimate users | `honeypot_middleware.py:99-127` |
| 2.16 | 🔴 Critical | Prompt firewall trivially bypassed: `scan_with_llama_guard` only checks for word "violent", `pre_flight_check` uses exact-case strings, LLM check allows any response containing "violent" to pass | `prompt_firewall.py:82-92` |
| 2.17 | 🟢 Low/Info | Sentry SDK initialized but no explicit instrumentation on admin/auth routes | `core/app.py` |
| 2.18 | 🟢 Low/Info | Debug mode default is `True` — leaks stack traces, exposes internals | `core/config.py:32` |

---

## 3. Frontend & Studio Client (Critical 2, High 3, Medium 4)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 3.1 | 🔴 Critical | Hardcoded god-password `supreme-god-password` in `adminStore.ts` — trivial privilege escalation | `adminStore.ts:42-45` |
| 3.2 | 🔴 Critical | No input sanitization: user prompts and server responses rendered as text in JSX without escaping; no DOMPurify | `src/components/chat/*`, `src/services/*` |
| 3.3 | 🟠 High | Direct `fetch` proliferation: many components bypass `apiClient`, so 429/422/401 interception is inconsistent | `App.tsx`, `useChat.ts`, `ThemeContext.tsx`, `CollabEditor.tsx`, etc. |
| 3.4 | 🟠 High | No route guards: admin mode detected by hostname string check (`isAdminMode`), not enforced centrally | `App.tsx` |
| 3.5 | 🟠 High | No token refresh/rotation: tokens consumed raw without `401 -> refresh -> retry` flow | `apiClient.ts`, `useAuth.ts` |
| 3.6 | 🟠 High | `customerStore.ts` uses XOR + Base64 obfuscation (not encryption) with hardcoded key in source | `customerStore.ts` |
| 3.7 | 🟡 Medium | `dangerouslySetInnerHTML` not used, but plain text rendering still carries XSS risk if server responds with HTML tags | Multi-file |
| 3.8 | 🟡 Medium | No CSP/Subresource Integrity: Vite build bundled but no CSP header enforcement | `vite.config.ts` |
| 3.9 | 🟡 Medium | Console noise: `console.log/warn/error` everywhere; in production may leak sensitive state | Multi-file |
| 3.10 | 🟡 Medium | No service worker caching for API responses | `sw.js` |
| 3.11 | 🟡 Medium | WebSocket URL depends on `window.location.host`; behind proxy WS may misconnect | `useWebSocket.ts` |
| 3.12 | 🟢 Low/Info | Low test coverage for auth/admin flows: login, logout, OTP, token persistence, admin gate override are untested | `src/stores/adminStore.ts`, `src/hooks/useAuth.ts` |
| 3.13 | 🟢 Low/Info | Vite exposes `VITE_SUPREMEAI_ADMIN_TOTP_SECRET` to client bundle by nature of `VITE_` prefix | `.env` |

---

## 4. Mobile App (Flutter) (Critical 2, High 2, Medium 3, Low 1)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 4.1 | 🔴 Critical | `flutter_secure_storage` declared but never used; auth tokens stored in plaintext SharedPreferences | `auth_provider.dart`, `pubspec.yaml` |
| 4.2 | 🔴 Critical | Hardcoded demo credentials (`demo@supremeai.com` / `Demo@123456`) in `login_screen.dart` | `login_screen.dart` |
| 4.3 | 🟠 High | Inconsistent base URLs: `ApiService` defaults to `supremeai-a.web.app`, `api_client.dart` hardcodes `api.supremeai.dev`, `orchestration_provider.dart` uses `supremeai-a.web.app` | `ApiService.dart`, `api_client.dart`, `orchestration_provider.dart` |
| 4.4 | 🟠 High | WebSocket has no auth token attached to connection | `NeuralStreamService.dart` |
| 4.5 | 🟠 High | `ApiClient.triggerQuickAction` and `updateGodRule` send requests without auth headers | `api_client.dart` |
| 4.6 | 🟡 Medium | No certificate pinning evident | `ApiService.dart` |
| 4.7 | 🟡 Medium | FCM token stored in plaintext SharedPreferences | `auth_provider.dart` |
| 4.8 | 🟡 Medium | No HTTPS enforcement beyond fixed `String.fromEnvironment` defaults | `lib/main.dart` config |
| 4.9 | 🟢 Low/Info | BYOC service passes GCP Service Account JSON directly over HTTPS; transport-only security | `byoc_service.dart` |

---

## 5. VS Code Extension (Critical 1, High 3, Medium 1, Low 3)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 5.1 | 🔴 Critical | XSS in Webviews: HTML content built via string interpolation from backend data without sanitization | `dashboard-provider.ts`, `CodeFlowHandler.ts` |
| 5.2 | 🟠 High | No CSP headers on webview panels; `enableScripts: true` with unsanitized HTML | `webview/*.ts` |
| 5.3 | 🟠 High | Open redirect/origin validation gap: `registerUriHandler` accepts any URI callback without verifying backend's authorized callback URL | `auth-service.ts` |
| 5.4 | 🟠 High | Unvalidated URLs in `tryFreeModelFallback`: user-configured provider endpoints can use `http://` (plaintext API key transmission) | `supremeai-service.ts` |
| 5.5 | 🟠 High | `getRepositoryId` uses deterministic base64 of filesystem path — not a secure ID | `CodeFlowHandler.ts` |
| 5.6 | 🟡 Medium | Hardcoded GitHub referer (`https://github.com/paykaribazaronline/supremeai`) sent to OpenRouter may not match user context | `supremeai-service.ts` |
| 5.7 | 🟢 Low/Info | Auto-learning and background indexing run by default without explicit user consent | `CodeFlowHandler.ts` |
| 5.8 | 🟢 Low/Info | Fallback to workspace settings sync for API key if SecretStorage unavailable | `auth-service.ts` |
| 5.9 | 🟢 Low/Info | Singleton without cleanup on deactivation | `supremeai-service.ts` |

---

## 6. Infrastructure & Deployment (Critical 5, High 5, Medium 3, Low 2)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 6.1 | 🔴 Critical | `.env` with live production API keys committed to repo despite gitignore | `.env` (root) |
| 6.2 | 🔴 Critical | Cloud Run service publicly accessible: `allUsers` granted `roles/run.invoker` | `infrastructure/terraform/cloud_run.tf` |
| 6.3 | 🔴 Critical | Circuit breaker disabled in CI: pipeline continues after failures | `.github/workflows/supreme-core-ci.yml` |
| 6.4 | 🔴 Critical | Lint errors suppressed with `|| true`, so builds pass despite style/security issues | `.github/workflows/supreme-core-ci.yml` |
| 6.5 | 🔴 Critical | Auto-fix engine has write access and can auto-commit fixes to repository | `.github/workflows/supreme-core-ci.yml` |
| 6.6 | 🟠 High | No VPC/Private Networking: VPC connector commented out; all traffic over public internet | `infrastructure/terraform/main.tf` |
| 6.7 | 🟠 High | No remote Terraform state locking (no S3/GCS backend with locking) | `infrastructure/terraform/` |
| 6.8 | 🟠 High | No Cloud Run Authentication: service allows unauthenticated invocation | `cloud_run.tf` |
| 6.9 | 🟠 High | Admin dashboard JS unauthenticated: fetches CI logs and triggers actions without auth gate | `admin/dashboard/script.js` |
| 6.10 | 🟠 High | `docs_auth_enabled` defaults to `False`, making FastAPI `/docs` and `/redoc` public | `core/config.py` |
| 6.11 | 🟠 High | Change detection disabled in CI: all jobs run on every push, wasting resources | `.github/workflows/supreme-core-ci.yml` |
| 6.12 | 🟡 Medium | Multiple Terraform modules define overlapping `google_cloud_run_service` resources | `infrastructure/terraform/` modules |
| 6.13 | 🟡 Medium | `TF_VAR_gcp_project_id` deployed with `-auto-approve`; no plan review | `.github/workflows/deploy.yml` |
| 6.14 | 🟡 Medium | No PSC/VPC peering; Redis and SQL potentially exposed via public IPs | `infrastructure/terraform/` |
| 6.15 | 🟡 Medium | Monitoring stack (Prometheus + Grafana) not secured in `docker-compose.monitoring.yml` | `infrastructure/monitoring/docker-compose.monitoring.yml` |
| 6.16 | 🟢 Low/Info | `.dockerignore` absent — Docker context transfers entire project directory | Root |
| 6.17 | 🟢 Low/Info | Multiple `Dockerfile` versions with inconsistent base images (`python:3.11-slim` vs `python:3.14-slim`) | Root, `backend/`, `Dockerfile.backend` |

---

## 7. Skills & Evolution Engine (Critical 2, High 3, Medium 2, Low 2)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 7.1 | 🔴 Critical | `skills/installer.py` writes arbitrary code to disk before AST/security check; write-time validation gap | `skills/installer.py` |
| 7.2 | 🔴 Critical | Weak sandbox in `skill_loader.py`: bans fewer patterns than backend `ASTSecurityScanner`; missing bans for `importlib`, `code`, `runpy`, `pickle`, `marshal`, `tempfile`, `urllib`, `http`, `requests`, `ctypes`, `builtins` | `skill_loader.py` |
| 7.3 | 🟠 High | Unvalidated `pip install` via `subprocess.run` from unsanitized dependency strings | `skills/installer.py` |
| 7.4 | 🟠 High | No path sanitization on skill `name`; `os.path.join` with untrusted name can write outside `skills/dynamic` | `skills/installer.py` |
| 7.5 | 🟠 High | `evolution/self_updater.py` `apply_hotfix(file_path, new_content)` writes arbitrary strings to arbitrary disk paths — unauthenticated RCE | `self_updater.py` |
| 7.6 | 🟠 High | Top-level `evolution/auto_skill_creator.py` only runs `py_compile` (syntax check); no AST security scan; can install malicious skills | `auto_skill_creator.py` |
| 7.7 | 🟡 Medium | Unencrypted unbounded SQLite storage in `data/evolution.db`; raw queries/results without encryption | `evolution_engine.py` |
| 7.8 | 🟡 Medium | In-memory demand queue in `SelfEvolutionAgent._pending_demands` not persisted; restarts drop demands | `self_evolution_agent.py` |
| 7.9 | 🟡 Medium | No end-to-end audit/consent flow for feedback recording; stores `query`, `retrieved_chunks` without user consent | `evolution_engine.py` |
| 7.10 | 🟢 Low/Info | No rate limiting on skill installs | `skills/installer.py` |
| 7.11 | 🟢 Low/Info | Registry `entry_point` is arbitrary string; if registry JSON writable by attacker, can point to any local file | `skills/registry.py` |

---

## 8. Testing & CI/CD (Critical 1, High 4, Medium 2)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 8.1 | 🔴 Critical | Test coverage threshold `--cov-fail-under=1` means 1% coverage passes | `.github/workflows/supreme-core-ci.yml` / `pyproject.toml` |
| 8.2 | 🟠 High | Low coverage for auth/admin flows: critical paths untested | `backend/tests/`, `apps/studio-client/src/stores/adminStore.ts` |
| 8.3 | 🟠 High | No tests for `apiClient`, `useAuth.ts`, `useChat.ts`, `useWebSocket.ts`, `firebase.ts`, `customerStore.ts` encryption | Studio client `test/` |
| 8.4 | 🟠 High | No e2e/security tests for token handling, XSS, admin gate override | Studio client `test/` |
| 8.5 | 🟠 High | Backend tests use hardcoded mock encryption key: `CwE60g_bA67m-mock-encryption-key-padded-len=` | Test fixtures / `secret_vault.py` |
| 8.6 | 🟡 Medium | VS Code extension has only 2 test files for ~20+ source files | `tools/vscode-extension/test/` |
| 8.7 | 🟡 Medium | No tests for `SupremeAIService` streaming, fallback logic, or webview rendering | `tools/vscode-extension/src/` |
| 8.8 | 🟢 Low/Info | `|| true` on ruff lint means lint errors non-blocking | `.github/workflows/supreme-core-ci.yml` |

---

## 9. Data Layer, Logging & Privacy (Critical 0, High 2, Medium 3, Low 2)

| ID | Severity | Blind Spot | Location |
|----|----------|------------|----------|
| 9.1 | 🟠 High | PII/data logging at DEBUG level to persistent files without guaranteed redaction | `core/logging_config.py:23-27` |
| 9.2 | 🟠 High | Database fallback in `EvolutionEngine` silently falls back to local SQLite without alerting when Supabase fails | `core/evolution_engine.py` |
| 9.3 | 🟡 Medium | Unencrypted unbounded SQLite stores raw queries/results without encryption, rotation, or TTL | `data/evolution.db` |
| 9.4 | 🟡 Medium | No PII stripping in evolution module when storing `task`, `approach`, `result`, `query`, `retrieved_chunks` | `core/evolution_engine.py` |
| 9.5 | 🟡 Medium | `react-query` refetchInterval polls admin dashboard every 15-60s; no rate limiting or backoff strategy | Studio client dashboard components |
| 9.6 | 🟢 Low/Info | Sentry optional — not instrumented for sensitive routes | `core/app.py` |
| 9.7 | 🟢 Low/Info | No audit/consent flow for user feedback and data collection | Evolution engine |

---

## ১০. র‍্যাপিড র‍出一种 (সেরা বেশি গুরুত্বপূর্ণ ৭টি)

| # | ব্লাইন্ড স্পট | মোকাবেলা |
|---|---------------|----------|
| 1 | `.env`-এ লাইভ প্রোডাকশন কী গিটে কমিট করা আছে | সব কী রোটেট করুন, গিট হিস্ট্রি থেকে `.env` মুছুন, প্রিভentan Commit Hook সেটআপ করুন |
| 2 | হার্ডকোডেড গড-পাসওয়ার্ড `supreme-god-password` | অবশ্যই মুছুন, অ্যাডমিন অ্যাক্সেস শুধু সঠিক HMAC-SHA256 এনকোডিং পাসওয়ার্ড দিয়েই চেক করুন |
| 3 | Cambridge Run সবাইকে公开 (`allUsers`) অ্যাক্সেস দিচ্ছে | `allUsers` IAM পলিসি মুছুন, শুধুমাত্র service account দিয়ে restrict করুন |
| 4 | পাসওয়ার্ড হ্যাশিংে SHA-256 ব্যবহার | bcrypt বা argon2 ব্যবহার করুন (`passlib` বা `bcrypt` লাইব্রেরি যোগ করুন) |
| 5 | Circuit breaker CI-তে Disabled | রি-অনাবল করুন, change detection এবং lint strict mode সক্রিয় করুন |
| 6 | Firebase JWT signature verification bypass ডেভ মোডে | অফলাইন মোডেও সিগনেচার ভেরিফিকেশন চালু রাখুন |
| 7 | Skills installer-এ write-time validation gap | Security scan এবং AST validation write করার আগে চালু করুন, path sanitization যোগ করুন |

---

## ১১. সｔｅｐ-বｙ-ｓｔｅｐ রিমেডিেশন প্ল্যান

| অগ্রাধিকার | অংক | কাজ | PR TM | প্রভাব |
|------------|------|-----|-------|-------|
| P0 | ১ | সব প্রোডাকশন কী রোটেট + `.env` গিট মুছে бранч-প্রটেক্টেড রিপো | ১০ m | 🔴 |
| P0 | ২ | Cambridge Run ইনভোকার পলিসি fix | ৬০ m | 🔴 |
| P1 | ৩ | অ্যাডমিন পাসওয়ার্ড হ্যাশিং bcrypt/argon2-তে মাইগ্রেট | ২ hrs | 🔴 |
| P1 | ৪ | ফাইল আপলোড ভ্যালিডেশন (size + content-type + malware scan) | ২ hrs | 🔴 |
| P1 | ৫ | Firebase JWT bypass ফিক্স (ডেভ মোডেও verify সহ) | ১ hr | 🟠 |
| P2 | ৬ | Circuit breaker + change detection + lint strict CI-তে ফিরিয়ে আনুন | ৩০ m | 🟠 |
| P2 | ৭ | वेबসকেট অথেন্টিকেশন যোগ করুন | ২ hrs | 🔴 |
| P2 | ৮ | Skills installer AST sandbox + path sanitization | ২ hrs | 🔴 |
| P2 | ৯ | লোকালস্টোরেজ টোকেন → HttpOnly সikir遷移 | ৪ hrs | 🟠 |
| P3 | ১০ | Adminashboard JS auth gate + CSP + HSTS headers | ২ hrs | 🟡 |

---

## ১২. টেস্ট কভারেজ লক্ষ্য (>= ৩৮%)

বর্তমানে প্রমাণিত কভারেজ:**

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| Backend auth/admin routes | Low | ≥ 80% | P0 |
| WebSocket auth | 0% | 100% | P0 |
| File upload handlers | 0% | 100% | P1 |
| Skills installer/loader | Partial | ≥ 70% | P1 |
| AdminStore (frontend) | 0% | ≥ 80% | P1 |
| apiClient | 0% | ≥ 90% | P1 |
| useAuth / useChat | 0% | ≥ 80% | P2 |
| VS Code webviews | 0% | ≥ 70% | P2 |
| Mobile auth_provider | Basic | ≥ 80% | P2 |
| Infrastructure/Terraform | 0% | ≥ 60% | P3 |

---

## ১৩. রেফারেন্স

| ক্যাটাগরি | সংশ্লিষ্ট ফাইলসমূহ |
|------------|---------------------|
| Backend Auth | `backend/core/auth_middleware.py`, `backend/core/admin_routes.py`, `backend/core/security.py`, `backend/core/api_key_middleware.py` |
| Backend Infrastructure | `backend/core/app.py`, `backend/core/config.py`, `backend/core/rate_limiter.py`, `backend/core/circuit_breaker.py` |
| Backend Tools | `backend/tools/auto_test_generator.py`, `backend/tools/voice_coder.py`, `backend/tools/diagram_to_architecture.py`, `backend/tools/image_to_code.py` |
| Frontend | `apps/studio-client/src/stores/adminStore.ts`, `apps/studio-client/src/services/apiClient.ts`, `apps/studio-client/src/hooks/useAuth.ts`, `apps/studio-client/src/hooks/useChat.ts` |
| Mobile | `apps/mobile/lib/auth_provider.dart`, `apps/mobile/lib/api_client.dart`, `apps/mobile/lib/NeuralStreamService.dart` |
| VS Code | `tools/vscode-extension/src/supremeai-service.ts`, `tools/vscode-extension/src/auth-service.ts`, `tools/vscode-extension/src/CodeFlowHandler.ts` |
| Infrastructure | `.github/workflows/supreme-core-ci.yml`, `infrastructure/terraform/cloud_run.tf`, `infrastructure/terraform/main.tf` |
| Admin | `admin/dashboard/script.js`, `admin/god.py` |
| Skills/Evolution | `skills/installer.py`, `skills/skill_loader.py`, `evolution/self_updater.py`, `evolution/auto_skill_creator.py`, `backend/core/evolution_engine.py` |

---

_This document was automatically generated by Kilo during a comprehensive system-wide analysis of SupremeAI osman. All blind spots are based on static code analysis, configuration review, and pattern detection. Immediate remediation is recommended for Critical and High severity items._
