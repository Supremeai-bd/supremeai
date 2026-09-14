/**
 * Playwright QA config — Part 2 of the QA engine plan, adapted to this repo.
 *
 * Role projects (guest / customer / admin / security) + auth setup projects.
 * The app under test comes from QA_BASE_URL (default http://127.0.0.1:3000 —
 * matches `vite preview --port 3000` used by the CI workflows; point it at a
 * deployed staging URL instead and the same suites run remotely).
 *
 * Auth: the customer/admin projects depend on setup projects that produce
 * storage states (qa/results/.auth/*.json). Setup skeletons live at
 * qa/playwright/customer/.auth/setup.ts and qa/playwright/admin/.auth/setup.ts
 * and must be completed before the authenticated projects can run.
 *
 * Run:  npx playwright test -c qa/playwright.config.qa.ts --project=guest
 */
import { defineConfig, devices } from "@playwright/test";
import { join } from "node:path";

const __qa = __dirname; // config lives at qa/playwright.config.qa.ts
const baseURL = process.env.QA_BASE_URL || "http://127.0.0.1:3000";
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: join(__qa, "playwright"),
  fullyParallel: true,
  forbidOnly: isCI,
  retries: 1,
  workers: isCI ? 2 : undefined,
  timeout: 30_000,

  reporter: [
    ["json", { outputFile: join(__qa, "results", "results.json") }],
    ...(isCI ? ([["github"]] as const) : ([["list"]] as const)),
    ["html", { open: "never", outputFolder: join(__qa, "results", "html") }],
  ],

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    navigationTimeout: 30_000,
    actionTimeout: 15_000,
  },

  projects: [
    // ── Setup projects (produce storage states for authenticated roles) ────
    {
      name: "setup-customer",
      testMatch: /customer\/\.auth\/.*\.setup\.ts/,
      use: { storageState: undefined },
    },
    {
      name: "setup-admin",
      testMatch: /admin\/\.auth\/.*\.setup\.ts/,
      use: { storageState: undefined },
    },

    // ── Guest (no auth) ────────────────────────────────────────────────────
    {
      name: "guest",
      testMatch: /guest\/.*\.spec\.ts/,
      testIgnore: /.*\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },

    // ── Customer (authenticated via setup-customer) ────────────────────────
    {
      name: "customer",
      testMatch: /customer\/.*\.spec\.ts/,
      testIgnore: /.*\.setup\.ts/,
      dependencies: ["setup-customer"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: join(__qa, "results", ".auth", "customer.json"),
      },
    },

    // ── Admin (step-up authenticated via setup-admin) ──────────────────────
    {
      name: "admin",
      testMatch: /admin\/.*\.spec\.ts/,
      testIgnore: /.*\.setup\.ts/,
      dependencies: ["setup-admin"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: join(__qa, "results", ".auth", "admin.json"),
      },
    },

    // ── Security (multi-context isolation checks; no shared storage) ───────
    {
      name: "security",
      testMatch: /security\/.*\.spec\.ts/,
      testIgnore: /.*\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
