import { defineConfig, devices } from '@playwright/test';

/**
 * আপনার Playwright E2E টেস্ট কনফিগারেশন
 * এটি স্বয়ংক্রিয়ভাবে ডেভ সার্ভার চালু করবে এবং তারপর E2E টেস্ট রান করবে।
 *
 * CI-তে রান করার জন্য: pnpm exec playwright test
 * লোকালে চালানোর জন্য: pnpm exec playwright test --headed
 */

// BASE_URL দূরবর্তী (production) হলে লোকাল ডেভ সার্ভার বুট না করে লাইভ সাইটেই টেস্ট চালায়।
const baseURL = process.env.BASE_URL || 'http://localhost:5173';
const startLocalServers =
  !/^https?:\/\//.test(baseURL) || baseURL.includes('localhost') || baseURL.includes('127.0.0.1');

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results/e2e-report.json' }],
    ['list'],
  ],
  expect: {
    // Visual Regression Test-এর জন্য ডিফল্ট সেটিংস
    toHaveScreenshot: { maxDiffPixels: 100, threshold: 0.2 },
  },

  use: {
    // বাংলা মন্তব্য: ডেভেলপমেন্ট সার্ভারের জন্য ডিফল্ট URL
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    ...(process.env.CI && process.env.GITHUB_REF && process.env.GITHUB_REF !== 'refs/heads/main' && !process.env.GITHUB_REF.startsWith('refs/tags/')
      ? []
      : [
          {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
          },
          {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
          },
          // মোবাইল ডিভাইসের জন্য টেস্ট
          {
            name: 'Mobile Chrome',
            use: { ...devices['Pixel 5'] },
          },
          {
            name: 'Mobile Safari',
            use: { ...devices['iPhone 12'] },
          },
        ]),
  ],

  // বাংলা মন্তব্য: ডেভেলপমেন্ট সার্ভার চালু করা, এটি ব্যাকগ্রাউন্ডে থাকবে সমস্ত টেস্ট জুড়ে
  // CI/CD-তে পোর্ট কনফ্লিক্ট এড়ানোর জন্য reuseExistingServer: true করা হয়েছে
  // দূরবর্তী BASE_URL (production monitoring) হলে লোকাল সার্ভার বুট করবে না
  webServer: startLocalServers
    ? [
    {
      command: 'cd frontend && pnpm dev --host 0.0.0.0 --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 120 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        VITE_USER_BACKEND: 'http://127.0.0.1:8000',
        VITE_ADMIN_BACKEND: 'http://127.0.0.1:8000',
        VITE_API_URL: 'http://127.0.0.1:8000'
      }
    },
    {
      command: 'cd backend && poetry run uvicorn main:app --port 8000',
      url: 'http://127.0.0.1:8000/docs',
      reuseExistingServer: true,
      timeout: 120 * 1000,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        USER_CORS_ORIGINS: 'http://localhost:5173,http://127.0.0.1:5173,https://supremeai-admin.web.app'
      }
    }
    ]
    : undefined,
});
