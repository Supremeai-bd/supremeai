import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
