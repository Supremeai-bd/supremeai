import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@supremeai/shared-types': new URL('../../packages/shared-types/src', import.meta.url).pathname,
      '@supremeai/ui-components': new URL('../../packages/ui-components/src', import.meta.url).pathname,
    },
  },
});
