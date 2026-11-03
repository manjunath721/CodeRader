import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
    // Polling: Docker Desktop Windows bind mounts don't reliably emit file
    // events, which left Vite serving stale transforms until restart.
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
