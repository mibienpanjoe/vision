import { expect, test } from "@playwright/test";

test.skip(!process.env.VISION_TEST_RESTORE_ORIGIN, "Requires the isolated packaged restore drill");

test("restored workspace keeps the surviving book and omits the deleted one", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const login = await page.request.post("/api/v1/auth/login", { headers: { Origin: process.env.VISION_TEST_RESTORE_ORIGIN! },
    data: { username: "package_reader", password: "synthetic package check passphrase" } });
  expect(login.status()).toBe(200);
  const books = (await (await page.request.get("/api/v1/works")).json()).items as { id: string; title: string }[];
  expect(books.map(book => book.title)).toEqual(["Packaged"]);
  const book = books[0];
  expect((await page.request.get(`/api/v1/works/${book.id}/original`)).status()).toBe(200);
  // A saved book opens for a new question without another upload.
  await page.goto(`/conversations/new?work=${book.id}`);
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
  await expect(page.getByLabel("Book file")).toHaveCount(0);
  page.on("console", entry => { if (entry.type() === "error") errors.push(entry.text()); });
  await page.setViewportSize({ width: 320, height: 850 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.local/restored-workspace.png", fullPage: true });
  expect(errors).toEqual([]);
});
