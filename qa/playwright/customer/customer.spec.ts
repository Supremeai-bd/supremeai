/**
 * Customer journey specs — qa/checklist/customer.yaml (C-01..C-10).
 *
 * These run under the `customer` project (storage state from setup-customer).
 * Most checks are implemented for real. The remaining test.fixme blocks are
 * gated on FEATURES that do not exist yet (not on selectors): /files has no
 * upload UI and /projects has no create-project UI (both are static module
 * pages) — instrumenting absent DOM would be dishonest. See
 * docs/audits/M0_G_QA_SPEC_COMPLETION.md for the per-test decision table.
 *
 * Auth guards under test (frontend/src/components/core/AuthGuards.tsx):
 *   - GuestRoute: authenticated /login|/register -> /workspace
 *   - ProtectedRoute: unauthenticated -> /login
 */
import { test, expect } from "@playwright/test";

test.describe("Customer journey (authenticated)", () => {
  // qa-id: C-01
  // Converted from fixme (M0-G): email-input/password-input/login-submit now
  // exist on LoginPage. Env prerequisites: QA_CUSTOMER_EMAIL/QA_CUSTOMER_PASSWORD
  // + a QA_BASE_URL deployment with a reachable auth backend (setup-customer).
  test(
    "C-01: login form authenticates customer into workspace",
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
  // Still fixme (M0-G): /files (WorkspaceModulePage module="files") is a static
  // module page — no upload UI (input[type=file], upload-btn/upload-submit)
  // exists to instrument, and the checklist requires backend storage evidence.
  // Needs the file-upload feature first; then set input files + upload-submit.
  test.fixme(
    "C-05: file upload stores file in backend — BLOCKED: /files has no upload UI to instrument (upload-btn/file-input/upload-submit) + needs reachable storage backend",
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
  // Still fixme (M0-G): /projects (WorkspaceModulePage module="projects") is a
  // static module page — there is no create-project control flow to attach
  // create-project-btn/project-name-input/create-project-submit to.
  // Needs the create-project feature first; the selectors below are the target.
  test.fixme(
    "C-08: created project persists after reload — BLOCKED: /projects has no create-project UI to instrument (create-project-btn/project-name-input/create-project-submit)",
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
  // Converted from fixme (M0-G): the GlobalHeader profile dropdown now exposes
  // account-menu-btn / logout-btn data-testids. The menu is closed by default,
  // so the body opens it before clicking logout.
  test("C-10: logout returns user to login", async ({ page }) => {
    await page.goto("/workspace");
    await page.locator('[data-testid="account-menu-btn"]').click();
    await page.locator('[data-testid="logout-btn"]').click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
