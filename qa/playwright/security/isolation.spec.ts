/**
 * Security isolation specs — qa/checklist/security.yaml (S-01..S-10).
 *
 * Grounded in:
 *   - AuthGuards.tsx: ProtectedRoute redirects anonymous users to /login
 *   - backend/api/routes/admin_v1.py: /api/v1/admin/* requires admin token
 *   - config_validation.py (Task-6 zero-hardcode): CORS is fail-closed, so a
 *     hostile Origin must never be reflected back as allowed
 *   - workspaceFeatureRoutes.tsx: /share/:shareId is public by design
 *
 * API checks use the Playwright `request` fixture relative to QA_BASE_URL —
 * the frontend origin proxies /api/** (vite preview/dev proxy; Firebase
 * Hosting rewrite in production), so same-origin API calls are realistic.
 *
 * Most checks are implemented for real. Remaining fixme blocks are gated on
 * FIXTURES/OPS EVIDENCE (two-user accounts, share fixtures, a captured
 * staging header baseline) — not on selectors. Per-test decisions:
 * docs/audits/M0_G_QA_SPEC_COMPLETION.md.
 */
import { test, expect } from "@playwright/test";

test.describe("Security isolation", () => {
  // qa-id: S-01
  test("S-01: anonymous user cannot open protected routes @smoke", async ({
    page,
  }) => {
    for (const route of ["/projects", "/files", "/settings/api-keys"]) {
      await page.goto(route);
      await expect(page, `visiting ${route} anonymously`).toHaveURL(/^\/login$/);
    }
  });

  // qa-id: S-02
  // Still fixme (M0-G): blocker is fixture work, not selectors — needs two
  // dedicated QA accounts (QA_USER_A/QA_USER_B) AND a stable project-id URL
  // scheme: the route graph has no /projects/:id route (catch-all 404 page),
  // so a status assertion cannot pass honestly yet.
  test.fixme(
    "S-02: user A cannot access user B project — BLOCKED: needs QA_USER_A/QA_USER_B accounts + stable project-id URL scheme (fixture work in next pass)",
    async ({ browser }) => {
      const ctxA = await browser.newContext();
      const ctxB = await browser.newContext();
      const pageA = await ctxA.newPage();
      const pageB = await ctxB.newPage();

      // loginAsUserA / createProject helpers arrive with the auth fixture pass
      const projectId = "user-a-project-id"; // placeholder until fixtures exist
      const resp = await pageB.goto(`/projects/${projectId}`);
      expect([403, 404]).toContain(resp?.status() ?? 404);

      await ctxA.close();
      await ctxB.close();
    },
  );

  // qa-id: S-03
  // Converted from fixme (M0-G): the AdminGate testids now exist and the body
  // builds the "Firebase-authenticated admin that has NOT stepped up" context
  // live (main login, no admin JWT — the security project uses no storage
  // state). It proves a deep link reaches the gate — never the console — and
  // that even stage-1 credentials leave the OTP challenge up with no console
  // data leaking. Env prerequisites: QA_ADMIN_EMAIL/QA_ADMIN_PASSWORD + live
  // backend answering otp_required.
  test("S-03: admin step-up cannot be bypassed by deep link", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.fill('[data-testid="email-input"]', process.env.QA_ADMIN_EMAIL ?? "");
    await page.fill('[data-testid="password-input"]', process.env.QA_ADMIN_PASSWORD ?? "");
    await page.click('[data-testid="login-submit"]');
    await page.waitForURL("**/workspace");

    // Deep link straight into /admin: the AdminGate (not the console) renders.
    await page.goto("/admin");
    await page.fill('[data-testid="admin-email-input"]', process.env.QA_ADMIN_EMAIL ?? "");
    await page.fill('[data-testid="admin-password-input"]', process.env.QA_ADMIN_PASSWORD ?? "");
    await page.click('[data-testid="admin-login-submit"]');
    // With a Firebase-authenticated admin session that has NOT stepped up,
    // the OTP/TOTP challenge stays up.
    await expect(page.locator('[data-testid="otp-input"]')).toBeVisible();
    const stats = await page.request.get("/api/v1/admin/stats");
    expect([401, 403]).toContain(stats.status());
  });

  // qa-id: S-04
  test("S-04: cors does not reflect arbitrary origins", async ({ request }) => {
    const hostile = "https://evil.example";
    const resp = await request.fetch("/", {
      method: "OPTIONS",
      headers: {
        Origin: hostile,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
      },
    });
    const acao = resp.headers()["access-control-allow-origin"];
    expect(
      acao,
      "access-control-allow-origin must never equal the hostile origin",
    ).not.toBe(hostile);
  });

  // qa-id: S-05
  test("S-05: protected api rejects unauthenticated calls", async ({
    request,
  }) => {
    const resp = await request.get("/api/v1/projects");
    expect([401, 403]).toContain(resp.status());
  });

  // qa-id: S-06
  // Still fixme (M0-G): blocker is fixture work — needs share-creation
  // fixtures for two users (a valid share id for user A's conversation plus a
  // marker conversation B must not leak). Not unblocked by selectors.
  test.fixme(
    "S-06: share links expose only the shared conversation — BLOCKED: needs share-creation fixtures for two users",
    async ({ page }) => {
      await page.goto("/share/valid-share-id"); // fixture required
      await expect(page.getByText("conversation-b-content-marker")).toHaveCount(0);
    },
  );

  // qa-id: S-07
  test("S-07: auth tokens never appear in urls", async ({ page }) => {
    for (const route of ["/", "/login", "/register"]) {
      await page.goto(route);
      expect(
        page.url(),
        `no token in URL on ${route}`,
      ).not.toMatch(/token=/i);
    }
  });

  // qa-id: S-08
  // Converted from fixme (M0-G): SecretsPage already carries the Part-9
  // key-creation testids (new-key-name / create-key-btn). The body now uses
  // them for real: creation is disabled until a name is filled (the draft
  // click-on-disabled-button would have timed out), then the one-time banner's
  // plaintext key must NOT survive a reload (masked list only). The literal
  // checklist assertion (no "sk-live") is kept alongside. Env prerequisites:
  // customer storage state (scratch QA account) + live /api/api-keys backend;
  // destructive only to the dedicated QA account's keys.
  test("S-08: api keys are masked after creation", async ({ page }) => {
    await page.goto("/settings/api-keys");
    await page.fill('[data-testid="new-key-name"]', `qa-mask-check-${Date.now()}`);
    await page.click('[data-testid="create-key-btn"]');
    // Created keys are shown exactly once in the one-time banner.
    const plaintextKey = (
      await page.locator("code").filter({ hasText: "sk-" }).textContent()
    )?.trim();
    expect(plaintextKey, "creation banner must show the full key once").toBeTruthy();

    await page.reload();
    const body = await page.content();
    expect(body).not.toContain("sk-live"); // checklist literal assertion
    expect(body, "plaintext key must never survive a reload").not.toContain(plaintextKey ?? "");
  });

  // qa-id: S-09
  // Still fixme (M0-G): blocker is OPS EVIDENCE, not code — the staging
  // header baseline (Firebase Hosting/Render) must be captured first
  // (08-production-preflight evidence) before hard assertions are enabled;
  // flipping this now would fake-green whatever headers happen to exist.
  test.fixme(
    "S-09: security headers baseline present on app responses — DEFERRED: capture staging header baseline before enabling hard assertions (08-production-preflight evidence)",
    async ({ request }) => {
      const resp = await request.get("/");
      expect(resp.headers()["x-content-type-options"]).toBeTruthy();
      expect(
        resp.headers()["x-frame-options"] ??
          resp.headers()["content-security-policy"],
      ).toBeTruthy();
    },
  );

  // S-10 is manual by design — no spec expected (see checklist manual_note).
});
