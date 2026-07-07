import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().optional(),
  VITE_APP_ENV: z.enum(["development", "staging", "production"]).default("development"),
});

const parsed = envSchema.safeParse({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? "",
  VITE_APP_ENV: import.meta.env.VITE_APP_ENV ?? "development",
});

if (!parsed.success) {
  throw new Error(`Invalid environment: ${parsed.error.message}`);
}

function resolveApiBaseUrl(configured: string | undefined): string {
  const origin = window.location.origin;
  const host = window.location.hostname;

  // GitHub Codespaces: browser must hit same-origin; Vite proxies /api → FastAPI.
  if (host.endsWith(".app.github.dev") || host.endsWith(".github.dev")) {
    return origin;
  }

  // frontend/.env often sets localhost — wrong when the UI is opened via a public URL.
  if (
    configured &&
    /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?\/?$/i.test(configured) &&
    !/^(localhost|127\.0\.0\.1)$/i.test(host)
  ) {
    return origin;
  }

  return configured || origin;
}

/** Use empty / unset VITE_API_BASE_URL for same-origin (Vite dev proxy). */
export const env = {
  apiBaseUrl: resolveApiBaseUrl(parsed.data.VITE_API_BASE_URL),
  appEnv: parsed.data.VITE_APP_ENV,
};
