import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(process.env.VISION_TEST_WORKSPACE !== "1", "Requires isolated workspace API/worker fixtures");

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("transport_reader");
  await page.getByLabel("Password", { exact: true }).fill("synthetic session transport passphrase");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
});

test("Unicode source spans stay exact and hostile-looking markup stays text", async ({ page }) => {
  test.setTimeout(60000);
  const prefix = 'é🦊é <img src=x onerror="alert(1)"> ';
  await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Unicode source reader");
  await page.getByLabel("Source file").setInputFiles({ name: "unicode.md", mimeType: "text/markdown", buffer: Buffer.from(`# Chapter 1\n\n${prefix}Élodie met Arthur.\n`) });
  await page.getByRole("button", { name: "Upload book", exact: true }).click();
  const book = page.getByRole("article", { name: "Unicode source reader" });
  await expect(book.locator(".readiness > div").nth(2)).toContainText("Ready", { timeout: 30000 });
  await book.getByRole("link", { name: "Open book" }).click();
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: "Through chapter 1" });
  await page.getByRole("button", { name: "Élodie", exact: true }).click();
  const response = page.waitForResponse(r => r.url().endsWith("/evidence"));
  await page.getByText("Source mentions", { exact: true }).click();
  await page.getByRole("button", { name: "Read passage 1", exact: true }).click();
  const view = await (await response).json();
  expect(view.span.start).toBe(Array.from(prefix).length);
  const reader = page.getByRole("region", { name: "Source reader", exact: true });
  await expect(reader.locator("mark")).toHaveText("Élodie");
  await expect(reader).toContainText(prefix.trim());
  await expect(reader.locator("img")).toHaveCount(0);
  await page.screenshot({ path: "../../.local/source-unicode.png", fullPage: true });
});

test("attribute and passage selections agree; real scope denial clears the excerpt", async ({ page }) => {
  test.setTimeout(60000);
  await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Attribute source reader");
  await page.getByLabel("Source file").setInputFiles({ name: "story.md", mimeType: "text/markdown", buffer: readFileSync("../api/tests/fixtures/narrative/story.md") });
  await page.getByRole("button", { name: "Upload book", exact: true }).click();
  const book = page.getByRole("article", { name: "Attribute source reader" });
  await expect(book.locator(".readiness > div").nth(2)).toContainText("Ready", { timeout: 30000 });
  await book.getByRole("link", { name: "Open book" }).click();
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: "Through chapter 3" });
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  await page.getByRole("button", { name: "Create visual specification", exact: true }).click();
  const inspector = page.getByRole("region", { name: "Attribute evidence" });
  const attribute = inspector.getByRole("button", { name: /Arthur · attire:/ });
  const resolved = page.waitForResponse(r => r.url().endsWith("/evidence"));
  await attribute.click();
  const view = await (await resolved).json();
  const reader = inspector.getByRole("region", { name: "Source reader" });
  await expect(reader.locator('mark[data-selected=true]')).toHaveText(view.span.quote);
  await reader.getByRole("button", { name: /Evidence for Arthur · attire/ }).click();
  await expect(attribute).toHaveAttribute("aria-pressed", "true");
  // Keep the real server boundary; send an inaccessible document revision.
  await page.route("**/api/v1/works/*/evidence", route => {
    const body = route.request().postDataJSON();
    return route.continue({ postData: JSON.stringify({ ...body, span: { ...body.span, document_revision_id: "00000000-0000-0000-0000-000000000000" } }) });
  });
  await inspector.getByRole("button", { name: /Arthur · left_cheek:/ }).click();
  await expect(reader.getByRole("alert")).toContainText("Resource not found");
  await expect(reader.locator(".source-excerpt")).toHaveCount(0);
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: "Through chapter 1" });
  await expect(inspector).toHaveCount(0);
});
