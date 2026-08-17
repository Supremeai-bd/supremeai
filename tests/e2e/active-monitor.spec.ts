import { test, expect, Page } from '@playwright/test';

// Configuration
const TEST_ADMIN_EMAIL = process.env.TEST_ADMIN_EMAIL || 'test_admin@supremeai.com';
const TEST_ADMIN_PASSWORD = process.env.TEST_ADMIN_PASSWORD || 'password123';
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'https://api.supremeai.com';
const SUPREMEAI_API_KEY = process.env.SUPREMEAI_API_KEY;

// Helper to report errors to the Admin Dashboard System Alerts
async function reportSystemAlert(page: Page, level: 'error' | 'warning', message: string) {
  console.log(`[Active Monitor] Found ${level}: ${message}`);
  
  if (!SUPREMEAI_API_KEY) {
    console.warn('[Active Monitor] SUPREMEAI_API_KEY is not set. Cannot send alert to dashboard.');
    return;
  }

  try {
    // We execute the fetch directly from Node.js (test context), not the browser
    const response = await fetch(`${INTERNAL_API_URL.replace(/\/$/, '')}/api/v1/admin/alerts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': SUPREMEAI_API_KEY
      },
      body: JSON.stringify({
        level,
        message: `🚨 **Browser Active Monitor:**\n\nClient-side ${level} detected:\n\`\`\`\n${message}\n\`\`\``
      })
    });
    
    if (!response.ok) {
      console.error(`[Active Monitor] Failed to send alert to backend: ${response.statusText}`);
    } else {
      console.log(`[Active Monitor] Successfully reported ${level} to Admin Dashboard.`);
    }
  } catch (err) {
    console.error('[Active Monitor] Network error when sending alert:', err);
  }
}

test.describe('Active Health Monitor (Production)', () => {
  test('Monitor Admin Dashboard for Client-Side Errors', async ({ page }) => {
    const caughtErrors: string[] = [];

    // 1. Setup Error Listeners
    page.on('console', async (msg) => {
      const type = msg.type();
      const text = msg.text();

      // বাংলা মন্তব্য: ব্রাউজার এক্সটেনশন (Fatkun, Pinterest, Facebook ইত্যাদি) থেকে আসা কনসোল এরর বাদ দিন
      const loc = msg.location();
      if (loc && loc.url && /extension:\/\//.test(loc.url)) return;

      // Ignore some common benign warnings or tracking errors
      if (text.includes('Failed to load resource: net::ERR_BLOCKED_BY_CLIENT')) return; // Adblock
      if (text.includes('favicon.ico')) return;
      
      if (type === 'error') {
        if (text.includes('Failed to load resource:')) return; // Ignore all network request failures logged to console (4xx/5xx)
        if (text.includes('net::ERR_ABORTED')) return; // Aborted SSE connections
        caughtErrors.push(`Console Error: ${text}`);
        await reportSystemAlert(page, 'error', text);
      } else if (type === 'warning' && text.includes('React Router')) {
        // Example: Catch important warnings like Router issues
        await reportSystemAlert(page, 'warning', text);
      }
    });

    page.on('pageerror', async (err) => {
      caughtErrors.push(`Uncaught Exception: ${err.message}`);
      await reportSystemAlert(page, 'critical', err.message);
    });

    page.on('requestfailed', async (request) => {
      const url = request.url();
      if (!url.includes('/api/v1/public/') && !url.includes('google-analytics') && !url.includes('/stream')) {
        const failure = request.failure()?.errorText || 'Unknown error';
        await reportSystemAlert(page, 'warning', `Network Request Failed: ${url} (${failure})`);
      }
    });

    // 2. Navigate to Admin Portal
    console.log('[Active Monitor] Navigating to Admin Portal...');
    await page.goto('/admin', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000); // Allow React to render first

    // 3. Login Flow
    // If the login form is visible, we need to log in
    if (await page.getByPlaceholder('Admin Email').isVisible()) {
      console.log('[Active Monitor] Attempting to login as test admin...');
      await page.getByPlaceholder('Admin Email').fill(TEST_ADMIN_EMAIL);
      await page.getByPlaceholder('Password').fill(TEST_ADMIN_PASSWORD);
      await page.getByRole('button', { name: 'Authorize Access' }).click();
      
      // Wait for navigation or error
      await page.waitForTimeout(5000); 
    }

    // 4. Verification
    // Check if we are inside the admin dashboard
    const isDashboardVisible = await page.getByText(/MODULE:/i).isVisible() || await page.getByText(/Supreme God Mode/i).isVisible() || await page.getByText(/SYSTEM ALERTS/i).isVisible();
    
    if (isDashboardVisible) {
      console.log('[Active Monitor] Successfully logged into Admin Dashboard.');
      
      // Click around to trigger lazy-loaded modules
      try {
        await page.getByText('SYSTEM ALERTS').click();
        await page.waitForTimeout(2000);
        await page.getByText('AI CORE').click();
        await page.waitForTimeout(2000);
      } catch (e) {
        console.log('[Active Monitor] Could not click modules, maybe layout changed.');
      }
    } else {
      console.log('[Active Monitor] Warning: Dashboard elements not found. Maybe still on login page or loading.');
    }

    // Give it a few seconds to catch any delayed React render errors
    await page.waitForTimeout(3000);
    // Fail the test if critical errors were found, so GitHub Actions knows
    if (caughtErrors.length > 0) {
      console.error('❌ CLIENT-SIDE ERRORS DETECTED:');
      caughtErrors.forEach((err, i) => console.error(`${i + 1}. ${err}`));
    }
    expect(caughtErrors.length, `Found ${caughtErrors.length} client-side errors during monitoring. Check Admin Dashboard Alerts for details.`).toBe(0);
  });
});
