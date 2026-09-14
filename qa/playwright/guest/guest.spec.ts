/**
 * Guest journey specs — qa/checklist/guest.yaml (G-01..G-10).
 *
 * Selectors are grounded in the REAL guest chat DOM
 * (frontend/src/pages/PublicPages.tsx, GuestChatPage):
 *   - form[aria-label="Guest chat"], textarea[aria-label="Message SupremeAI"]
 *   - submit button aria-label "Send message", disabled when input empty
 *   - "Save this chat" renders as <a href="/register"> once a message exists
 *   - guest chat replies are generated locally (650ms typing delay) — no
 *     backend dependency, so these tests run against a static preview build.
 */
import { test, expect } from "@playwright/test";

test.describe("Guest journey", () => {
  // qa-id: G-01
  test("G-01: guest chat surface loads at root @smoke", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/^\/$/);
    await expect(page.locator('form[aria-label="Guest chat"]')).toBeVisible();
    await expect(
      page.locator('textarea[aria-label="Message SupremeAI"]'),
    ).toBeVisible();
  });

  // qa-id: G-02
  test("G-02: empty submit is disabled", async ({ page }) => {
    await page.goto("/");
    const send = page.locator('button[aria-label="Send message"]');
    await expect(send).toBeVisible();
    await expect(send).toBeDisabled();
  });

  // qa-id: G-03
  test("G-03: enter sends message and conversation view appears", async ({
    page,
  }) => {
    await page.goto("/");
    const input = page.locator('textarea[aria-label="Message SupremeAI"]');
    await input.fill("Hello SupremeAI");
    await input.press("Enter");
    // The composer is local state: sending reveals the temporary-conversation strip.
    await expect(
      page.getByText("Your conversation is temporary").first(),
    ).toBeVisible();
    await expect(input).toHaveValue("");
  });

  // qa-id: G-04
  test("G-04: shift+enter creates a newline without sending", async ({
    page,
  }) => {
    await page.goto("/");
    const input = page.locator('textarea[aria-label="Message SupremeAI"]');
    await input.click();
    await input.press("Shift+Enter");
    await expect(input).toHaveValue("\n");
    // Conversation strip must still be hidden (nothing was sent).
    await expect(page.getByText("Your conversation is temporary")).toHaveCount(0);
  });

  // qa-id: G-05
  test("G-05: guest header exposes Sign in and Get started", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.locator('a[href="/login"]')).toBeVisible();
    await expect(page.locator('a[href="/register"]').first()).toBeVisible();
  });

  // qa-id: G-06
  test("G-06: model picker opens in guest chat", async ({ page }) => {
    await page.goto("/");
    const trigger = page.locator(
      'form[aria-label="Guest chat"] button[aria-expanded]',
    );
    await expect(trigger).toBeVisible();
    await trigger.click();
    await expect(
      page.locator('form[aria-label="Guest chat"] button[aria-expanded="true"]'),
    ).toBeVisible();
  });

  // qa-id: G-07
  test("G-07: new chat resets the conversation", async ({ page }) => {
    await page.goto("/");
    const input = page.locator('textarea[aria-label="Message SupremeAI"]');
    await input.fill("Hello SupremeAI");
    await input.press("Enter");
    await expect(
      page.getByText("Your conversation is temporary").first(),
    ).toBeVisible();
    await page.locator('button[aria-label="Start a new chat"]').click();
    await expect(page.getByText("Your conversation is temporary")).toHaveCount(0);
  });

  // qa-id: G-08
  test("G-08: public info pages render without auth", async ({ page }) => {
    for (const route of ["/models", "/pricing", "/docs"]) {
      const resp = await page.goto(route);
      expect(resp?.status(), `GET ${route}`).toBe(200);
      await expect(page).toHaveURL(new RegExp(`^${route}$`));
      // never bounced to the login wall
      await expect(page).not.toHaveURL(/\/login/);
    }
  });

  // qa-id: G-09
  test("G-09: bangla input is accepted", async ({ page }) => {
    await page.goto("/");
    const input = page.locator('textarea[aria-label="Message SupremeAI"]');
    await input.fill("তুমি কি বাংলায় কথা বলতে পারো?");
    await expect(input).toHaveValue(/বাংলা/);
  });

  // qa-id: G-10
  test("G-10: save chat CTA sends guest to register", async ({ page }) => {
    await page.goto("/");
    const input = page.locator('textarea[aria-label="Message SupremeAI"]');
    await input.fill("Hello SupremeAI");
    await input.press("Enter");
    const saveChat = page.locator('a[href="/register"]', {
      hasText: "Save this chat",
    });
    await expect(saveChat).toBeVisible();
    await saveChat.click();
    await expect(page).toHaveURL(/\/register$/);
  });
});
