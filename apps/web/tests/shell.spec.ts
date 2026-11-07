import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => route.fulfill({ json: { id: "00000000-0000-4000-8000-000000000001", username: "synthetic" } }));
  await page.route("**/api/v1/auth/workspace", route => route.fulfill({ json: { id: "00000000-0000-4000-8000-000000000001", username: "synthetic" } }));
  await page.route("**/api/v1/conversations?*", route => route.fulfill({ json: { items: [], next_cursor: null } }));
});

test("retired library, book and preview routes are gone", async ({ request }) => {
  for (const path of ["/library", "/works/00000000-0000-4000-8000-000000000001", "/preview/conversation"]) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
});

test("conversation shell opens dark by default and persists an explicit theme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/conversations/new");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
  await expect(page.locator("html")).toHaveClass("dark");
  await page.getByRole("button", { name: "Switch color theme" }).click();
  await expect(page.locator("html")).toHaveClass("light");
  await page.reload();
  await expect(page.locator("html")).toHaveClass("light");
  await expect(page.getByLabel("Username")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);
});

test("shell remains usable at narrow widths and by keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/conversations/new");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to conversation" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("fonts and approved icons are served locally in both themes", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("/conversations/new");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
  await page.evaluate(async () => {
    await document.fonts.ready;
    await document.fonts.load('13px "Geist Mono"');
  });
  const fonts = await page.evaluate(() => Array.from(document.fonts).filter(f => f.status === "loaded").map(f => f.family));
  expect(fonts).toEqual(expect.arrayContaining(["Inter", "Source Serif 4", "Geist Mono"]));
  for (const path of ["/favicon.ico", "/apple-icon.png", "/manifest.webmanifest", "/brand/icon-192.png", "/brand/icon-512.png", "/notices/inter-OFL.txt"]) {
    expect((await request.get(path)).status(), path).toBe(200);
  }
  await page.getByRole("button", { name: "Switch color theme" }).click();
  await expect(page.locator("html")).toHaveClass("light");
  await page.screenshot({ path: "../../.local/vision-shell-light.png", fullPage: true });
  await page.getByRole("button", { name: "Switch color theme" }).click();
  await expect(page.locator("html")).toHaveClass("dark");
  await page.screenshot({ path: "../../.local/vision-shell-dark.png", fullPage: true });
  await page.setViewportSize({ width: 320, height: 720 });
  await page.screenshot({ path: "../../.local/vision-shell-narrow.png", fullPage: true });
  expect(errors.filter(error => !error.includes("401 (Unauthorized)"))).toEqual([]);
});
