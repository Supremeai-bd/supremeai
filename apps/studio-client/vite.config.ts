// ============================================================================
// file >> vite.config.ts
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> vite.config.ts
// ============================================================================
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  base: './', // Important for Electron to load local files
  plugins: [
    react(),
    tailwindcss()
  ],
})
