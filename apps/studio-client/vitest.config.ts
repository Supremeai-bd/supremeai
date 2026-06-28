import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  resolve: {
    // বাংলা মন্তব্য: মনোরিপোর অন্যান্য প্রোজেক্টের React 18-এর সাথে সংঘর্ষ এড়াতে এবং টেস্টে React 19 নিশ্চিত করতে লোকাল পাথ সেট করা হলো
    alias: {
      'react': path.resolve(__dirname, './node_modules/react'),
      'react-dom': path.resolve(__dirname, './node_modules/react-dom'),
    },
    dedupe: ['react', 'react-dom'],
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/components/customer/**/*.{ts,tsx}', 'src/hooks/**/*.{ts,tsx}'],
      exclude: ['**/*.d.ts', '**/test/**', '**/*.test.*'],
    },
  },
});
