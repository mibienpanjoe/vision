import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => route.fulfill({ status: 401, json: { error: { code: "AUTHENTICATION_REQUIRED", message: "Sign in required." } } }));
});

test("library shell opens dark by default and persists an explicit theme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to your library", exact: true, level: 1 })).toBeVisible();
  await expect(page.locator("html")).toHaveClass("dark");
  const theme = page.getByRole("combobox", { name: "Color theme" });
  await expect(theme).toBeEnabled();
  await theme.selectOption("light");
  await expect(page.locator("html")).toHaveClass("light");
  await page.reload();
  await expect(theme).toHaveValue("light");
  await expect(page.locator("html")).toHaveClass("light");
  await expect(page.getByRole("heading", { name: "Sign in to your library" })).toBeVisible();
});

test("shell remains usable at narrow widths and by keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to library" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("fonts and approved icons are served locally in both themes", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("/");
  await page.evaluate(async () => {
    await document.fonts.ready;
    await document.fonts.load('13px "Geist Mono"');
  });
  const fonts = await page.evaluate(() => Array.from(document.fonts).filter(f => f.status === "loaded").map(f => f.family));
  expect(fonts).toEqual(expect.arrayContaining(["Inter", "Source Serif 4", "Geist Mono"]));
  for (const path of ["/favicon.ico", "/apple-icon.png", "/manifest.webmanifest", "/brand/icon-192.png", "/brand/icon-512.png", "/notices/inter-OFL.txt"]) {
    expect((await request.get(path)).status(), path).toBe(200);
  }
  const theme = page.getByRole("combobox", { name: "Color theme" });
  await theme.selectOption("system");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveClass("light");
  await page.screenshot({ path: "../../.local/vision-shell-light.png", fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass("dark");
  await page.screenshot({ path: "../../.local/vision-shell-dark.png", fullPage: true });
  await page.setViewportSize({ width: 320, height: 720 });
  await page.screenshot({ path: "../../.local/vision-shell-narrow.png", fullPage: true });
  expect(errors.filter(error => !error.includes("401 (Unauthorized)"))).toEqual([]);
});

test("sign-in panel fits a laptop viewport with larger text", async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 744 });
  await page.goto("/");
  await page.addStyleTag({ content: "html { font-size: 20px; }" });
  const panel = page.getByRole("region", { name: "Sign in to your library" });
  await expect(panel).toBeInViewport({ ratio: 1 });
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeInViewport({ ratio: 1 });
});

test("sign-in trims copied username whitespace and preserves the password", async ({ page }) => {
  await page.route("**/api/v1/works", route => route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.route("**/api/v1/auth/login", async route => {
    expect(route.request().postDataJSON()).toEqual({ username: "book-test", password: " synthetic passphrase " });
    await route.fulfill({ json: { id: "00000000-0000-0000-0000-000000000001", username: "book-test" } });
  });
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill(" book-test ");
  await page.getByLabel("Password", { exact: true }).fill(" synthetic passphrase ");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Upload a book", exact: true })).toBeVisible();
});
