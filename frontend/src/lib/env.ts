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

/** Use empty string to mean same-origin (Vite dev proxy). */
export const env = {
  apiBaseUrl: parsed.data.VITE_API_BASE_URL || window.location.origin,
  appEnv: parsed.data.VITE_APP_ENV,
};
