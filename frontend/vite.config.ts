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
    host: "0.0.0.0",
    port: 5173,
    // Required for GitHub Codespaces forwarded URLs (*.app.github.dev)
    allowedHosts: [".github.dev", ".app.github.dev", "localhost", "127.0.0.1"],
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:9000",
        changeOrigin: true,
      },
    },
  },
});
