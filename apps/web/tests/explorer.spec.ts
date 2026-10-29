import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(process.env.VISION_TEST_WORKSPACE !== "1", "Requires the isolated workspace API and worker harness");
test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("transport_reader");
  await page.getByLabel("Password", { exact: true }).fill("synthetic session transport passphrase");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
});

test("real upload produces scoped entities; late aliases and stale detail disappear on cutoff change", async ({ page }) => {
  test.setTimeout(60000);
  await page.getByRole("textbox", { name: "Book title", exact: true }).fill("The annotated world");
  await page.getByLabel("Source file").setInputFiles({ name: "story.md", mimeType: "text/markdown", buffer: readFileSync("../api/tests/fixtures/narrative/story.md") });
  await page.getByRole("button", { name: "Upload book", exact: true }).click();
  const book = page.getByRole("article", { name: "The annotated world" });
  await expect(book.locator(".readiness > div").nth(2)).toContainText("Ready", { timeout: 30000 });
  await book.getByRole("link", { name: "Open book" }).click();
  await expect(page.getByRole("heading", { name: "The annotated world" })).toBeVisible();
  const boundary = page.getByRole("combobox", { name: "Reading boundary", exact: true });
  await expect(boundary).toHaveValue("");
  await expect(page.getByRole("button", { name: "Arthur", exact: true })).toHaveCount(0);
  await boundary.selectOption({ label: "Whole book" });
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
  const details = page.getByRole("region", { name: "Entity details" });
  await expect(details).toContainText("Wren · supported alias");
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  await boundary.selectOption({ label: "Through chapter 2" });
  await expect(details).toHaveCount(0);
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
  await expect(details).not.toContainText("Wren · supported alias");
  await expect(page.getByLabel("Story moment", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Scene context", { exact: true })).toHaveValue("");
  await page.getByLabel("Find an entity").fill("captain");
  await expect(page.getByRole("button", { name: "Mira", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Brann", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mira", exact: true }).click();
  await expect(details).toContainText("Identity unresolved");
  await expect(details.getByRole("button", { name: "Choose Brann" })).toBeVisible();
  await details.getByRole("button", { name: "Choose Brann" }).click();
  await expect(details.getByRole("heading", { name: "Brann", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "../../.local/explorer-narrow.png", fullPage: true });
});

test("chosen entity, moment, context and cutoff reach the stored request", async ({ page }) => {
  await page.getByRole("article", { name: "The annotated world" }).getByRole("link", { name: "Open book" }).click();
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: "Through chapter 3" });
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  const response = page.waitForResponse(r => /\/visualizations$/.test(r.url()) && r.request().method() === "POST");
  await page.getByRole("button", { name: "Create visual specification", exact: true }).click();
  const result = await (await response).json();
  expect(result.visualization).not.toBeNull();
  const stored = await (await page.request.get(`/api/v1/works/${result.visualization.work_id}/visualizations/${result.visualization.id}`)).json();
  expect(stored.request.entity_id).toBe(result.result.data.subject.entity.entity_ids[0]);
  expect(stored.request.moment).toEqual({ kind: "phrase", text: "after the war" });
  expect(stored.request.context).toBe("at home");
  expect(stored.request.through_chapter_id).toBe(result.result.data.scope.through_chapter_id);
  await expect(page.getByRole("status").filter({ hasText: "Saved visual specification" })).toBeVisible();
});
