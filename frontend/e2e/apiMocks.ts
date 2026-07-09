import type { Page } from "@playwright/test";
import type { UserProfile } from "../src/lib/auth/types";
import { mockDashboardResponses } from "../src/mocks/fixtures";

const MOCK_ACCESS_TOKEN = "mock-access-token";

/** MSW-compatible auth API mocks for Sprint 0 Playwright (cookie + JSON refresh). */
export async function installAuthApiMocks(page: Page, profile: UserProfile) {
  const tokenBody = {
    access_token: MOCK_ACCESS_TOKEN,
    expires_in: 300,
    token_type: "bearer",
  };

  await page.route("**/api/v1/refresh", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 200, json: tokenBody });
  });

  await page.route("**/api/v1/profile", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 200, json: profile });
  });

  await page.route("**/api/v1/login", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      json: { ...tokenBody, refresh_token: "mock-refresh-token" },
    });
  });

  await page.route("**/api/v1/logout", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 200, json: { message: "Successfully logged out" } });
  });

  if (profile.role === "user") {
    await page.route("**/api/v1/dashboard/user/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/overview")) {
        await route.fulfill({
          status: 200,
          json: mockDashboardResponses.overview(profile),
        });
        return;
      }
      if (url.includes("/activity")) {
        await route.fulfill({ status: 200, json: mockDashboardResponses.activity });
        return;
      }
      if (url.includes("/sessions")) {
        await route.fulfill({ status: 200, json: mockDashboardResponses.sessions });
        return;
      }
      await route.continue();
    });
  }
}

export async function seedRefreshCookie(page: Page) {
  await page.context().addCookies([
    {
      name: "refresh_token",
      value: "mock-refresh-token",
      domain: "127.0.0.1",
      path: "/api/v1",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    },
  ]);
}
