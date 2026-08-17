import { test, expect } from '@playwright/test';

test.describe('User Authentication Flow', () => {
  test('should show validation errors on empty submit', async ({ page }) => {
    // VITE_PORTAL_TYPE is 'user' by default
    await page.goto('/login');
    
    // Verify neon heading is visible
    await expect(page.getByText('SUPREME AI')).toBeVisible();

    // Click submit without filling anything
    await page.getByRole('button', { name: 'INITIALIZE SESSION' }).click();

    // Verify error message
    await expect(page.getByText('দয়া করে সব ফিল্ড পূরণ করুন।')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill the login form
    await page.getByPlaceholder('Email / Identity').fill('invalid@example.com');
    await page.getByPlaceholder('Passphrase').fill('wrongpassword');

    // Submit
    await page.getByRole('button', { name: 'INITIALIZE SESSION' }).click();

    // Verify backend error or general error shows up
    await expect(page.locator('text=/Error:/i')).toBeVisible({ timeout: 10000 });
  });

  test('navigation to register page works', async ({ page }) => {
    await page.goto('/login');
    
    // Click Sign Up link
    await page.getByRole('link', { name: 'Sign Up' }).click();

    // Should navigate to register
    await expect(page).toHaveURL(/.*\/register/);
  });
});
