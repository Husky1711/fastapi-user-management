import { defineConfig, devices } from "@playwright/test";

const host = "127.0.0.1";
const port = Number(process.env.VITE_DEV_PORT || 5173);
const useRealApi = process.env.E2E_REAL_API === "1";
const baseURL = process.env.E2E_BASE_URL || `http://${host}:${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: !useRealApi,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: useRealApi
    ? undefined
    : {
        command: "npm run dev",
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          ...process.env,
          VITE_DEV_PORT: String(port),
        },
      },
});
