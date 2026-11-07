import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");
const OUT = "../../.local/q49";

test("complete path: open, attach and ask, moment, refine, copy, generate, sources, close and resume", async ({ page, browser }) => {
  test.setTimeout(180000);
  mkdirSync(OUT, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(page).toHaveURL(/\/conversations\/new$/);
  await expect(page.getByLabel("Username")).toHaveCount(0);
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Arthur after the war at home");
  await input.press("Enter");
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  await page.getByRole("group", { name: "Other moments" }).getByRole("button", { name: /^war/ }).click();
  await expect(prompt).toContainText("steel armor", { timeout: 60000 });
  await input.fill("as a charcoal sketch");
  await input.press("Enter");
  await expect(prompt).toContainText("charcoal sketch", { timeout: 60000 });
  await page.getByRole("button", { name: "Copy prompt", exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await prompt.textContent());
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.getByRole("img", { name: /Generated image for prompt version 3/ })).toBeVisible({ timeout: 60000 });
  const sources = page.getByRole("button", { name: "Sources", exact: true });
  await sources.click();
  await expect(page.getByRole("dialog", { name: "Sources" }).locator("mark").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sources).toBeFocused();
  const url = page.url();
  const finalPrompt = await prompt.textContent();
  for (const [scheme, width] of [["dark", 1440], ["light", 1440], ["dark", 390], ["light", 320]] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `${OUT}/flow-${scheme}-${width}.png`, fullPage: true });
  }
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `${OUT}/flow-200pct-320.png`, fullPage: true });
  // Close the browser tab entirely, then resume from a fresh page in the same workspace.
  const state = await page.context().storageState();
  await page.close();
  const resumed = await (await browser.newContext({ storageState: state })).newPage();
  await resumed.goto(url);
  await expect(resumed.getByTestId("active-prompt")).toHaveText(finalPrompt!);
  await expect(resumed.getByRole("img", { name: /prompt version 3/ })).toBeVisible();
  await expect(resumed.getByRole("list", { name: "Conversation messages" }).getByText("Show war", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
