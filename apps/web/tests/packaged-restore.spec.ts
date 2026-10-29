import { expect, test } from "@playwright/test";

test.skip(!process.env.VISION_TEST_RESTORE_ORIGIN, "Requires the isolated packaged restore drill");

test("restored library and entity explorer render surviving data and omit the deleted book", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Username").fill("package_reader");
  await page.getByLabel("Password", { exact: true }).fill("synthetic package check passphrase");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const book = page.getByRole("article", { name: "Packaged", exact: true });
  await expect(book).toBeVisible();
  // The signed-out session probe intentionally answers 401; inspect console errors after authentication settles.
  page.on("console", entry => { if (entry.type() === "error") errors.push(entry.text()); });
  await expect(page.getByRole("article", { name: "Delete after snapshot" })).toHaveCount(0);
  await expect(book.locator(".readiness > div").nth(2)).toContainText("Ready");
  await page.screenshot({ path: "../../.local/restored-library.png", fullPage: true });
  await book.getByRole("link", { name: "Open book" }).click();
  await expect(page.getByRole("heading", { name: "Packaged", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: "Whole book" });
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
  await expect(page.getByRole("region", { name: "Entity details" })).toContainText("Arthur");
  const evidence = page.waitForResponse(response => response.url().endsWith("/evidence"));
  await page.getByText("Source mentions", { exact: true }).click();
  await page.getByRole("button", { name: "Read passage 1", exact: true }).click();
  const resolved = await evidence;
  expect(resolved.status()).toBe(200);
  const span = (await resolved.json()).span;
  const reader = page.getByRole("region", { name: "Source reader", exact: true });
  await expect(reader.locator("mark").first()).toHaveText(span.quote);
  await page.setViewportSize({ width: 320, height: 850 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.local/restored-book.png", fullPage: true });
  await reader.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "../../.local/restored-evidence.png" });
  expect(errors).toEqual([]);
});
