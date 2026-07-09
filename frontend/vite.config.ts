import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import type { ProxyOptions } from "vite";

// Ports: keep in sync with codespaces.ports.env
const DEFAULT_UI_PORT = 5173;
const DEFAULT_API_PORT = 9000;

function apiProxy(target: string): Record<string, ProxyOptions> {
  return {
    "/api": {
      target,
      changeOrigin: true,
      secure: false,
      configure: (proxy) => {
        proxy.on("proxyRes", (proxyRes) => {
          const raw = proxyRes.headers["set-cookie"];
          if (!raw) {
            return;
          }
          const cookies = Array.isArray(raw) ? raw : [raw];
          proxyRes.headers["set-cookie"] = cookies.map((cookie) =>
            cookie.replace(/;\s*Secure/gi, "").replace(/Domain=[^;]+/gi, ""),
          );
        });
      },
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const uiPort = Number(env.VITE_DEV_PORT || DEFAULT_UI_PORT);
  const apiTarget =
    env.VITE_API_PROXY_TARGET || `http://localhost:${DEFAULT_API_PORT}`;
  const proxy = apiProxy(apiTarget);

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: "0.0.0.0",
      port: uiPort,
      strictPort: true,
      allowedHosts: [".github.dev", ".app.github.dev", "localhost", "127.0.0.1"],
      proxy,
    },
    preview: {
      host: "127.0.0.1",
      port: uiPort,
      strictPort: true,
      proxy,
    },
  };
});
