/**
 * Auth setup — CUSTOMER role (produces qa/results/.auth/customer.json).
 *
 * SKELETON (Task 7-e): the login automation is intentionally not implemented
 * yet. It needs (a) the QA_CUSTOMER_EMAIL / QA_CUSTOMER_PASSWORD secrets and
 * (b) the Part-9 data-testid attributes on the login form
 * (email-input / password-input / login-submit — see
 * docs/plans/features/qa_engine_auto_checking_implementation_plan.md Part 9).
 *
 * Until then this setup fails with an explicit TODO so the customer project
 * cannot silently run without auth. Implement it as:
 *
 *   await page.goto('/login');
 *   await page.fill('[data-testid="email-input"]', email);
 *   await page.fill('[data-testid="password-input"]', password);
 *   await page.click('[data-testid="login-submit"]');
 *   await page.waitForURL('**/workspace');
 *   await page.context().storageState({ path: STORAGE_STATE });
 */
import { test as setup } from "@playwright/test";

const STORAGE_STATE = "qa/results/.auth/customer.json";

setup("authenticate as QA customer", async () => {
  const email = process.env.QA_CUSTOMER_EMAIL;
  const password = process.env.QA_CUSTOMER_PASSWORD;
  if (!email || !password) {
    throw new Error(
      "TODO(auth): QA_CUSTOMER_EMAIL / QA_CUSTOMER_PASSWORD are not set. " +
        "Create a dedicated non-production QA account and expose the values " +
        "as environment variables before running the customer project.",
    );
  }
  throw new Error(
    `TODO(auth): customer login automation pending Part-9 data-testid instrumentation ` +
      `(credentials present for ${email ? "QA_CUSTOMER_EMAIL" : "missing"}). ` +
      `Implement per the comment block at the top of qa/playwright/customer/.auth/setup.ts ` +
      `so storage state lands in ${STORAGE_STATE}.`,
  );
});
