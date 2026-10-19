import { expect, test } from "@playwright/test";

test("library shell has no invented books and persists an explicit theme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your library" })).toBeVisible();
  await expect(page.locator("html")).toHaveClass("dark");
  const theme = page.getByRole("combobox", { name: "Color theme" });
  await expect(theme).toBeEnabled();
  await theme.selectOption("light");
  await expect(page.locator("html")).toHaveClass("light");
  await page.reload();
  await expect(theme).toHaveValue("light");
  await expect(page.locator("html")).toHaveClass("light");
  await expect(page.getByText("Book uploads are not available yet.")).toBeVisible();
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
