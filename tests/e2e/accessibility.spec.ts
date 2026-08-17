import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility Tests (WCAG)', () => {
    test('Homepage should not have any automatically detectable accessibility issues', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('[data-testid="dashboard-sidebar"]', { state: 'visible', timeout: 15000 });

        const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

        // কোনো ভায়োলেশন থাকলে তা প্রিন্ট করার জন্য একটি সহায়ক লগ
        if (accessibilityScanResults.violations.length > 0) {
            console.log('Accessibility violations found on homepage:', JSON.stringify(accessibilityScanResults.violations, null, 2));
        }

        expect(accessibilityScanResults.violations).toEqual([]);
    });

    test('Admin Dashboard should be accessible', async ({ page }) => {
        await page.goto('/admin'); // আপনার অ্যাডমিন পেজের URL
        await page.waitForSelector('text=Admin Gate', { state: 'visible', timeout: 15000 });

        const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

        expect(accessibilityScanResults.violations).toEqual([]);
    });
});
