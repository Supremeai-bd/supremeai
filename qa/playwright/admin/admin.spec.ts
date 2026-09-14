/**
 * Admin journey specs — qa/checklist/admin.yaml (A-01..A-10).
 *
 * The admin console lives entirely under /admin (ProtectedRoute ->
 * RoleGuard(requiredRole=admin) -> AdminShell with OTP/TOTP step-up).
 * Admin API behavior is grounded in backend/api/routes/admin_v1.py:
 * router prefix /api/v1 with dependencies=[Depends(require_admin_token), ...].
 *
 * URL/status-based checks are implemented for real; step-up and panel checks
 * that need admin credentials + Part-9 data-testid are explicit test.fixme.
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
  test.fixme(
    "A-02: step-up OTP/TOTP challenge gates the console — BLOCKED: needs QA_ADMIN_* secrets + otp-input/otp-submit data-testid (Part 9)",
    async ({ page }) => {
      await page.goto("/login");
      await page.fill('[data-testid="email-input"]', process.env.QA_ADMIN_EMAIL ?? "");
      await page.fill('[data-testid="password-input"]', process.env.QA_ADMIN_PASSWORD ?? "");
      await page.click('[data-testid="login-submit"]');
      await page.goto("/admin");
      await expect(page.locator('[data-testid="otp-input"]')).toBeVisible();
      // No console data may leak before step-up completes.
      const stats = await page.request.get("/api/v1/admin/stats");
      expect([401, 403]).toContain(stats.status());
    },
  );

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
  test.fixme(
    "A-06: overview sub-tab renders without shell crash — BLOCKED: AdminConsole internals lack data-testid (admin-shell/admin-kpi); needs admin storage state",
    async ({ page }) => {
      await page.goto("/admin");
      await expect(page.locator('[data-testid="admin-shell"]')).toBeVisible();
      await expect(page.locator('[data-testid="admin-kpi"]').first()).toBeVisible();
    },
  );

  // qa-id: A-07
  test.fixme(
    "A-07: sub-tab navigation switches panels — BLOCKED: sub-tab controls lack data-testid; needs admin storage state",
    async ({ page }) => {
      await page.goto("/admin");
      await page.locator('[data-testid="admin-users-tab"]').click(); // selector pending Part 9
      await expect(page.locator('[data-testid="user-list"]')).toBeVisible();
    },
  );

  // A-08, A-09, A-10 are manual by design — no spec expected (see checklist manual_note).
});
