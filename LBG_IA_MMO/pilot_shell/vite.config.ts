import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendProxy = process.env.VITE_BACKEND_PROXY || "http://127.0.0.1:8000";
const mmoProxy = process.env.VITE_MMO_PROXY || "http://127.0.0.1:8080";
const companionProxy = process.env.VITE_COMPANION_PROXY || "http://127.0.0.1:8065";

export default defineConfig({
  plugins: [react()],
  base: "/pilot/v2/",
  build: {
    outDir: "../pilot_web/v2",
    emptyOutDir: true,
  },
  server: {
    port: 5175,
    strictPort: true,
    host: true,
    proxy: {
      "/v1": {
        target: backendProxy,
        changeOrigin: true,
      },
      "/metrics": {
        target: backendProxy,
        changeOrigin: true,
      },
      "/mmo": {
        target: mmoProxy,
        changeOrigin: true,
      },
      "/companion-api": {
        target: companionProxy,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/companion-api/, ""),
      },
    },
  },
});
