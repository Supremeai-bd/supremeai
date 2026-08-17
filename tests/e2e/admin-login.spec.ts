import { test, expect } from '@playwright/test';

test.describe('Admin Authentication Flow', () => {
  // Note: This test requires VITE_PORTAL_TYPE=admin to be set during build/dev
  test('should show validation errors on empty submit', async ({ page }) => {
    await page.goto('/admin');
    
    // Check if we got redirected to user portal due to wrong env
    if (page.url().endsWith('/login') || page.url().endsWith('/workspace')) {
      test.skip(true, 'Skipping admin test because VITE_PORTAL_TYPE is not admin');
      return;
    }

    // Verify admin heading is visible
    await expect(page.getByText('SupremeAI Admin Gate')).toBeVisible();

    // Click submit without filling anything
    await page.getByRole('button', { name: 'Authorize Access' }).click();

    // Verify HTML5 validation or custom error
    await expect(page.locator('input:invalid')).toHaveCount(2); // Email and password are required
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/admin');

    if (page.url().endsWith('/login') || page.url().endsWith('/workspace')) {
      test.skip(true, 'Skipping admin test because VITE_PORTAL_TYPE is not admin');
      return;
    }

    // Fill the login form
    await page.getByPlaceholder('Admin Email').fill('invalid@supremeai.com');
    await page.getByPlaceholder('Password').fill('wrongpassword123');

    // Submit
    await page.getByRole('button', { name: 'Authorize Access' }).click();

    // Verify backend error or general error shows up
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[role="alert"]')).toContainText(/failed|invalid/i);
  });
});
