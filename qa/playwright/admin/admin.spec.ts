/**
 * Admin journey specs — qa/checklist/admin.yaml (A-01..A-10).
 *
 * The admin console lives entirely under /admin (ProtectedRoute ->
 * RoleGuard(requiredRole=admin) -> AdminShell with OTP/TOTP step-up).
 * Admin API behavior is grounded in backend/api/routes/admin_v1.py:
 * router prefix /api/v1 with dependencies=[Depends(require_admin_token), ...].
 *
 * Most checks are implemented for real. The step-up flow runs against the
 * REAL AdminGate DOM (components/admin/auth/AdminLogin.tsx: admin-email-input /
 * admin-password-input / admin-login-submit -> otp-input / otp-submit) — the
 * Part-9 testids now exist. Remaining fixme is gated on fixture work (JWT
 * transport verification), not selectors. Per-test decisions:
 * docs/audits/M0_G_QA_SPEC_COMPLETION.md.
 */
import { test, expect } from "@playwright/test";

test.describe("Admin journey", () => {
  // qa-id: A-01
  test("A-01: unauthenticated /admin access is denied @smoke", async ({
    page,
  }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/^\/login$/);
  });

  // qa-id: A-02
  // Converted from fixme (M0-G): the Part-9 testids exist on both the main
  // login form and the AdminGate. The body drives the REAL two-stage flow
  // (main login -> /admin gate credentials -> OTP challenge), which is what
  // the app actually renders. Env prerequisites: QA_ADMIN_EMAIL/
  // QA_ADMIN_PASSWORD + a live backend that answers otp_required for the QA
  // admin (same contract setup-admin exercises).
  test("A-02: step-up OTP/TOTP challenge gates the console", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.fill('[data-testid="email-input"]', process.env.QA_ADMIN_EMAIL ?? "");
    await page.fill('[data-testid="password-input"]', process.env.QA_ADMIN_PASSWORD ?? "");
    await page.click('[data-testid="login-submit"]');
    await page.waitForURL("**/workspace");

    // Deep-linking /admin as an admin without a step-up session shows the
    // AdminGate credential form, NOT the console.
    await page.goto("/admin");
    await page.fill('[data-testid="admin-email-input"]', process.env.QA_ADMIN_EMAIL ?? "");
    await page.fill('[data-testid="admin-password-input"]', process.env.QA_ADMIN_PASSWORD ?? "");
    await page.click('[data-testid="admin-login-submit"]');
    await expect(page.locator('[data-testid="otp-input"]')).toBeVisible();
    // No console data may leak before step-up completes.
    const stats = await page.request.get("/api/v1/admin/stats");
    expect([401, 403]).toContain(stats.status());
  });

  // qa-id: A-03
  test("A-03: step-up admin reaches the console", async ({ page }) => {
    // Requires the admin storage state produced by setup-admin.
    await page.goto("/admin");
    await expect(page).toHaveURL(/^\/admin/);
    await expect(page).not.toHaveURL(/^\/login$/);
  });

  // qa-id: A-04
  test("A-04: admin api rejects unauthenticated requests", async ({
    request,
  }) => {
    // /api/v1/admin/stats is a real admin alias endpoint (require_admin_token).
    const resp = await request.get("/api/v1/admin/stats");
    expect([401, 403]).toContain(resp.status());
  });

  // qa-id: A-05
  // Still fixme (M0-G): blocker is fixture/verification work, not selectors —
  // a customer JWT must be extracted from the auth storage state and the token
  // transport (Bearer header vs cookie) verified before this can assert 403
  // honestly. Part 9 "fixture work in a later pass".
  test.fixme(
    "A-05: admin api rejects authenticated non-admin token — BLOCKED: customer JWT transport (Bearer header vs cookie) not yet verified",
    async ({ request }) => {
      const token = process.env.QA_CUSTOMER_TOKEN; // to be extracted from auth storage in a later pass
      const resp = await request.get("/api/v1/admin/stats", {
        headers: { Authorization: `Bearer ${token ?? ""}` },
      });
      expect(resp.status()).toBe(403);
    },
  );

  // qa-id: A-06
  // Converted from fixme (M0-G): admin-shell (AdminAuthenticated) and
  // admin-kpi (overview Dashboard KPI cards) testids now exist. Env
  // prerequisites: stepped-up admin storage state from setup-admin (which
  // needs QA_ADMIN_* + live backend).
  test("A-06: overview sub-tab renders without shell crash", async ({
    page,
  }) => {
    await page.goto("/admin");
    await expect(page.locator('[data-testid="admin-shell"]')).toBeVisible();
    await expect(page.locator('[data-testid="admin-kpi"]').first()).toBeVisible();
  });

  // qa-id: A-07
  // Converted from fixme (M0-G): nav action buttons now carry
  // data-testid="admin-<actionId>-tab" (RoleAwareNavRail). The "users" panel is
  // the registry's Tenants / RBAC sub-tab (actionId tenants-rbac ->
  // UserManager), so the selector is admin-tenants-rbac-tab — grounded in the
  // real navigationRegistry, unlike the draft "admin-users-tab" guess. The
  // registry list container carries user-list. Needs the setup-admin storage
  // state (env creds + live backend).
  test("A-07: sub-tab navigation switches panels", async ({ page }) => {
    await page.goto("/admin");
    await page.locator('[data-testid="admin-tenants-rbac-tab"]').click();
    await expect(page.locator('[data-testid="user-list"]')).toBeVisible();
  });

  // A-08, A-09, A-10 are manual by design — no spec expected (see checklist manual_note).
});
