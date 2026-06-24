import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Tauri expects that there are no processes on port 1420
    // if this port is in use, another error will be thrown
    strictPort: true,
    strictPort: true,
    port: 1420,
  },
  // to make use of `TAURI_PLATFORM`, `TAURI_ARCH`, `TAURI_FAMILY`,
  // `TAURI_PLATFORM_VERSION`, `TAURI_PLATFORM_VARIANT`, `TAURI_ARCH`
  // environment variables
  define: {
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_PLATFORM": JSON.stringify(process.env.TAURI_PLATFORM),
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_ARCH": JSON.stringify(process.env.TAURI_ARCH),
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_FAMILY": JSON.stringify(process.env.TAURI_FAMILY),
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_PLATFORM_VERSION": JSON.stringify(process.env.TAURI_PLATFORM_VERSION),
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_PLATFORM_VARIANT": JSON.stringify(process.env.TAURI_PLATFORM_VARIANT),
    // @ts-expect-error process is a nodejs global
    "import.meta.env.VITE_TAURI_ARCH": JSON.stringify(process.env.TAURI_ARCH),
  },
  // optimize deps for faster startup
  // https://vitejs.dev/config/#deps-optimize
  optimizeDeps: {
    exclude: ["@tauri-apps/api"],
  },
})
