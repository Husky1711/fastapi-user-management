import { expect, test } from "@playwright/test";
import { installAuthApiMocks, seedRefreshCookie } from "./apiMocks";
import { mockUserProfile } from "../src/mocks/fixtures";

test.describe("Sprint 0 auth E2E", () => {
  test("#6 user visiting /admin is redirected to unauthorized", async ({ page }) => {
    const profile = mockUserProfile("user");
    await installAuthApiMocks(page, profile);
    await seedRefreshCookie(page);

    await page.goto("/admin");

    await expect(page).toHaveURL(/\/unauthorized$/);
    await expect(page.getByTestId("unauthorized-page")).toBeVisible();
    await expect(page.getByRole("heading", { name: /403/ })).toBeVisible();
    await expect(page.getByText(/Signed in as testuser/i)).toBeVisible();
  });

  test("#7 reload with refresh cookie bootstraps without login form", async ({ page }) => {
    const profile = mockUserProfile("user");
    await installAuthApiMocks(page, profile);
    await seedRefreshCookie(page);

    await page.goto("/dashboard");
    await expect(page.getByTestId("login-page")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

    await page.reload();
    await expect(page.getByTestId("login-page")).toHaveCount(0);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });
});
