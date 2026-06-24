import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    port: 1420,
  },
  define: {
    "import.meta.env.VITE_TAURI_PLATFORM": JSON.stringify(process.env.TAURI_PLATFORM),
    "import.meta.env.VITE_TAURI_ARCH": JSON.stringify(process.env.TAURI_ARCH),
    "import.meta.env.VITE_TAURI_FAMILY": JSON.stringify(process.env.TAURI_FAMILY),
    "import.meta.env.VITE_TAURI_PLATFORM_VERSION": JSON.stringify(process.env.TAURI_PLATFORM_VERSION),
    "import.meta.env.VITE_TAURI_PLATFORM_VARIANT": JSON.stringify(process.env.TAURI_PLATFORM_VARIANT),
  },
  optimizeDeps: {
    exclude: ["@tauri-apps/api"],
  },
})
