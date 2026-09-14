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
  test.fixme(
    "S-03: admin step-up cannot be bypassed by deep link — BLOCKED: needs QA_ADMIN_* secrets + otp-input data-testid (Part 9)",
    async ({ page }) => {
      // With a Firebase-authenticated admin session that has NOT stepped up:
      await page.goto("/admin");
      await expect(page.locator('[data-testid="otp-input"]')).toBeVisible();
      const stats = await page.request.get("/api/v1/admin/stats");
      expect([401, 403]).toContain(stats.status());
    },
  );

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
  test.fixme(
    "S-08: api keys are masked after creation — BLOCKED: needs key-creation data-testid + scratch QA account",
    async ({ page }) => {
      await page.goto("/settings/api-keys");
      await page.click('[data-testid="create-key-btn"]'); // selector pending Part 9
      await page.reload();
      const body = await page.content();
      expect(body).not.toContain("sk-live");
    },
  );

  // qa-id: S-09
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
