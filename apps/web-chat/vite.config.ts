// ============================================================================
// file >> vite.config.ts
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> vite.config.ts
// ============================================================================
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@supremeai/shared-types': new URL('../../packages/shared-types/src', import.meta.url).pathname,
      '@supremeai/ui-components': new URL('../../packages/ui-components/src', import.meta.url).pathname,
    },
  },
  server: {
    proxy: {
      '/task': 'http://127.0.0.1:8000',
      '/skills': 'http://127.0.0.1:8000',
    },
  },
});
