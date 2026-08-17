import { test, expect } from '@playwright/test';

test.describe('SupremeAI Nexus E2E Flow', () => {

  test('should load the dashboard and verify Java Worker widget', async ({ page }) => {
    // 1. Load the admin dashboard
    await page.goto('/admin'); // Assumes routing allows direct /admin access

    // 2. Verify Nexus Header exists
    await expect(page.getByText('SupremeAI')).toBeVisible();

    // 3. Verify Java Background Worker widget is rendered
    const workerWidget = page.locator('text=Java Background Worker');
    await expect(workerWidget).toBeVisible({ timeout: 10000 });

    // 4. Verify healthy status indicator
    await expect(page.locator('text=HEALTHY').first()).toBeVisible();

    // 5. Verify metrics blocks are present (CPU, Memory, Active Tasks)
    await expect(page.locator('text=CPU Load')).toBeVisible();
    await expect(page.locator('text=Memory')).toBeVisible();
    await expect(page.locator('text=Active Tasks')).toBeVisible();
  });

  test('should be able to submit an orchestration command via chat', async ({ page }) => {
    await page.goto('/admin');

    // Find the chat input
    const chatInput = page.getByPlaceholder('[SupremeAI Nexus Command...]');
    await expect(chatInput).toBeVisible();

    // Type a command that would theoretically trigger a background Java task
    await chatInput.fill('Run full system security audit');
    await chatInput.press('Enter');

    // Verify the message appears in the chat stream
    await expect(page.getByText('Admin: Run full system security audit')).toBeVisible();

    // Verify SupremeAI's immediate ACK response appears
    await expect(page.getByText('Processing command "Run full system security audit"... Authorization confirmed.')).toBeVisible();
  });

});
