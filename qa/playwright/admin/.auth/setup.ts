/**
 * Auth setup — ADMIN role (produces qa/results/.auth/admin.json).
 *
 * SKELETON (Task 7-e): admin auth is a TWO-stage flow and neither stage is
 * automated yet:
 *   1. Firebase login on /login (needs QA_ADMIN_EMAIL / QA_ADMIN_PASSWORD and
 *      the Part-9 data-testid attributes on the login form).
 *   2. Step-up inside AdminShell at /admin — OTP/TOTP challenge
 *      (needs QA_ADMIN_TOTP_SECRET to derive a current code, or QA_ADMIN_OTP
 *      if a static dev code is provisioned; plus otp-input/otp-submit
 *      data-testid attributes — see Part 9).
 *
 * The plan's caution applies: QA_ADMIN_* must be a DEDICATED QA admin
 * account, never the real production admin.
 *
 * Once implemented the final step must persist storage state:
 *   await page.context().storageState({ path: STORAGE_STATE });
 */
import { test as setup } from "@playwright/test";

const STORAGE_STATE = "qa/results/.auth/admin.json";

setup("authenticate as QA admin (login + step-up)", async () => {
  const email = process.env.QA_ADMIN_EMAIL;
  const password = process.env.QA_ADMIN_PASSWORD;
  const otp = process.env.QA_ADMIN_OTP ?? process.env.QA_ADMIN_TOTP_SECRET;
  if (!email || !password || !otp) {
    throw new Error(
      "TODO(auth): QA_ADMIN_EMAIL / QA_ADMIN_PASSWORD / QA_ADMIN_TOTP_SECRET (or QA_ADMIN_OTP) " +
        "are not set. Use a DEDICATED QA admin account — never production credentials.",
    );
  }
  throw new Error(
    "TODO(auth): admin login + OTP/TOTP step-up automation pending Part-9 data-testid " +
      "instrumentation (otp-input/otp-submit). Implement per the comment block at the top of " +
      `qa/playwright/admin/.auth/setup.ts so storage state lands in ${STORAGE_STATE}.`,
  );
});
