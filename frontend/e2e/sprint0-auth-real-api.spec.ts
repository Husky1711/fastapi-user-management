import { expect, test, type Page } from "@playwright/test";

const realApiEnabled = process.env.E2E_REAL_API === "1";
const e2eUser = process.env.E2E_USER || "testuser";
const e2ePassword = process.env.E2E_PASSWORD || "user123";

async function loginViaUi(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(e2eUser);
  await page.getByLabel("Password").fill(e2ePassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("login-page")).toHaveCount(0, { timeout: 30_000 });
  await expect(page).toHaveURL(/\/(dashboard|admin|org-admin|super-admin)/, {
    timeout: 30_000,
  });
}

test.describe("Sprint 0 real API E2E", () => {
  test.skip(!realApiEnabled, "Set E2E_REAL_API=1 to run against a deployed API");
  test.describe.configure({ mode: "serial", timeout: 90_000 });

  test("#6 user visiting /admin is redirected to unauthorized", async ({ page }) => {
    test.skip(e2eUser !== "testuser", "Use E2E_USER=testuser for RBAC #6");

    await loginViaUi(page);
    await page.goto("/admin");

    await expect(page).toHaveURL(/\/unauthorized$/, { timeout: 30_000 });
    await expect(page.getByTestId("unauthorized-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: /403/ })).toBeVisible();
    await expect(page.getByText(/Signed in as testuser/i)).toBeVisible();
  });

  test("#7 reload with refresh cookie bootstraps without login form", async ({ page }) => {
    await loginViaUi(page);

    await page.goto("/dashboard");
    await expect(page.getByTestId("login-page")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: 30_000,
    });

    await page.reload();
    await expect(page.getByTestId("login-page")).toHaveCount(0, { timeout: 30_000 });
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: 30_000,
    });
  });
});
