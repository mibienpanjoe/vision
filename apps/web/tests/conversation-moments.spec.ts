import { expect, test, type Page } from "@playwright/test";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

async function ready(page: Page) {
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
}

for (const width of [320, 390, 1280]) {
  test(`moments wrap, select by keyboard and announce the outcome at ${width}px`, async ({ page }) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width, height: 800 });
    await ready(page);
    const group = page.getByRole("group", { name: "Other moments" });
    await expect(group.locator("[aria-current=true]")).toContainText("dinner");
    await expect(group.getByRole("button")).toHaveCount(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.locator(".conversation-variants img, .conversation-variants svg")).toHaveCount(0);
    if (width === 320) {
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: "../../.local/q44/moments-320-200pct.png", fullPage: true });
      await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
    }
    const war = group.getByRole("button", { name: /^war/ });
    await war.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("active-prompt")).toContainText("steel armor", { timeout: 60000 });
    await expect(page.getByRole("status").filter({ hasText: "Now showing war." })).toHaveCount(1);
    await expect(group.locator("[aria-current=true]")).toContainText("war");
  });
}

test("touch selection is the same single action and a stale tab keeps the usable prompt", async ({ browser }) => {
  test.setTimeout(120000);
  const context = await browser.newContext({ hasTouch: true, viewport: { width: 390, height: 800 } });
  const page = await context.newPage();
  await ready(page);
  const prompt = await page.getByTestId("active-prompt").textContent();
  const other = await context.newPage();
  await other.goto(page.url());
  await page.getByRole("group", { name: "Other moments" }).getByRole("button", { name: /^war/ }).tap();
  await expect(page.getByTestId("active-prompt")).toContainText("steel armor", { timeout: 60000 });
  await other.getByRole("group", { name: "Other moments" }).getByRole("button", { name: /^child/ }).tap();
  await expect(other.getByRole("status").filter({ hasText: "previous prompt is unchanged" })).toHaveCount(1);
  await expect(other.getByTestId("active-prompt")).toHaveText(prompt!);
  await context.close();
});
