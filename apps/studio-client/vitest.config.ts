// ============================================================================
// file >> vitest.config.ts
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> vitest.config.ts
// ============================================================================
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
  },
});
