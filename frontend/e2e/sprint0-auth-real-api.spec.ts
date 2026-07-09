import { expect, test, type Page } from "@playwright/test";

const realApiEnabled = process.env.E2E_REAL_API === "1";
const e2eUser = process.env.E2E_USER || "testuser";
const e2ePassword = process.env.E2E_PASSWORD || "user123";

async function loginViaApi(page: Page) {
  await page.goto("/login");
  const ok = await page.evaluate(
    async ({ username, password }) => {
      const response = await fetch("/api/v1/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      return response.ok;
    },
    { username: e2eUser, password: e2ePassword },
  );
  expect(ok).toBeTruthy();

  const cookies = await page.context().cookies();
  expect(cookies.some((cookie) => cookie.name === "refresh_token")).toBeTruthy();
}

test.describe("Sprint 0 real API E2E", () => {
  test.skip(!realApiEnabled, "Set E2E_REAL_API=1 to run against a deployed API");
  test.describe.configure({ mode: "serial", timeout: 60_000 });

  test("#6 user visiting /admin is redirected to unauthorized", async ({ page }) => {
    test.skip(e2eUser !== "testuser", "Use E2E_USER=testuser for RBAC #6");

    await loginViaApi(page);
    await page.goto("/admin");

    await expect(page).toHaveURL(/\/unauthorized$/);
    await expect(page.getByTestId("unauthorized-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: /403/ })).toBeVisible();
    await expect(page.getByText(/Signed in as testuser/i)).toBeVisible();
  });

  test("#7 reload with refresh cookie bootstraps without login form", async ({ page }) => {
    await loginViaApi(page);

    await page.goto("/dashboard");
    await expect(page.getByTestId("login-page")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: 20_000,
    });

    await page.reload();
    await expect(page.getByTestId("login-page")).toHaveCount(0, { timeout: 20_000 });
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: 20_000,
    });
  });
});
