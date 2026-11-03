import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Capacitor serves the bundle from an app-local URL, so assets must be relative.
  base: "./",
  server: { host: "127.0.0.1" },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    reportCompressedSize: false,
    sourcemap: false,
  },
});
