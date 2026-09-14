/**
 * Customer journey specs — qa/checklist/customer.yaml (C-01..C-10).
 *
 * These run under the `customer` project (storage state from setup-customer).
 * URL/status-based checks are implemented for real; checks that need the
 * Part-9 data-testid instrumentation or live backend storage are explicit
 * test.fixme blocks with the blocker recorded in the checklist manual_note.
 *
 * Auth guards under test (frontend/src/components/core/AuthGuards.tsx):
 *   - GuestRoute: authenticated /login|/register -> /workspace
 *   - ProtectedRoute: unauthenticated -> /login
 */
import { test, expect } from "@playwright/test";

test.describe("Customer journey (authenticated)", () => {
  // qa-id: C-01
  test.fixme(
    "C-01: login form authenticates customer into workspace — BLOCKED: needs data-testid (email-input/password-input/login-submit) + QA customer credentials",
    async ({ page }) => {
      await page.goto("/login");
      await page.fill('[data-testid="email-input"]', process.env.QA_CUSTOMER_EMAIL ?? "");
      await page.fill('[data-testid="password-input"]', process.env.QA_CUSTOMER_PASSWORD ?? "");
      await page.click('[data-testid="login-submit"]');
      await expect(page).toHaveURL(/\/workspace/);
    },
  );

  // qa-id: C-02
  test("C-02: session survives a full page reload", async ({ page }) => {
    await page.goto("/workspace");
    await expect(page).not.toHaveURL(/\/login/); // storage state must authenticate us
    await page.reload();
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page).toHaveURL(/\/workspace/);
  });

  // qa-id: C-03
  test("C-03: authenticated user is bounced away from /login", async ({
    page,
  }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/workspace/);
  });

  // qa-id: C-04
  test("C-04: projects page loads for authenticated customer @smoke", async ({
    page,
  }) => {
    const resp = await page.goto("/projects");
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveURL(/^\/projects$/);
    await expect(page).not.toHaveURL(/\/login/);
  });

  // qa-id: C-05
  test.fixme(
    "C-05: file upload stores file in backend — BLOCKED: needs data-testid (upload-btn/file-input) + reachable storage backend",
    async ({ page }) => {
      await page.goto("/files");
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: "qa-test.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("QA test file content"),
      });
      await page.click('[data-testid="upload-submit"]');
      await expect(page.getByText("qa-test.txt").first()).toBeVisible();
      await page.reload();
      await expect(page.getByText("qa-test.txt").first()).toBeVisible();
    },
  );

  // qa-id: C-06
  test("C-06: api keys page loads for authenticated customer", async ({
    page,
  }) => {
    const resp = await page.goto("/settings/api-keys");
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveURL(/^\/settings\/api-keys$/);
    await expect(page).not.toHaveURL(/\/login/);
  });

  // qa-id: C-07
  test("C-07: ai studio live workspace loads", async ({ page }) => {
    const resp = await page.goto("/workspace/live");
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveURL(/^\/workspace\/live$/);
    await expect(page).not.toHaveURL(/\/login/);
  });

  // qa-id: C-08
  test.fixme(
    "C-08: created project persists after reload — BLOCKED: needs data-testid (create-project-btn/project-name-input/create-project-submit)",
    async ({ page }) => {
      const projectName = `QA-Project-${Date.now()}`;
      await page.goto("/projects");
      await page.click('[data-testid="create-project-btn"]');
      await page.fill('[data-testid="project-name-input"]', projectName);
      await page.click('[data-testid="create-project-submit"]');
      await expect(page.getByText(projectName).first()).toBeVisible();
      await page.reload();
      await expect(page.getByText(projectName).first()).toBeVisible();
    },
  );

  // qa-id: C-09
  test("C-09: usage cost dashboard loads", async ({ page }) => {
    const resp = await page.goto("/usage");
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveURL(/^\/usage$/);
    await expect(page).not.toHaveURL(/\/login/);
  });

  // qa-id: C-10
  test.fixme(
    "C-10: logout returns user to login — BLOCKED: logout control in GlobalHeader lacks a stable selector",
    async ({ page }) => {
      await page.goto("/workspace");
      await page.locator('[data-testid="logout-btn"]').click(); // selector pending Part 9
      await expect(page).toHaveURL(/\/login$/);
    },
  );
});
