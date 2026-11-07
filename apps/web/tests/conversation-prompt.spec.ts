import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

test("the prompt is primary; copy and export are exact; Enter sends and typing continues during work", async ({ page }) => {
  test.setTimeout(90000);
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Arthur after the war at home");
  await input.press("Enter");
  await expect(input).toBeFocused();
  await input.pressSequentially("next idea");
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  await expect(input).toHaveValue("next idea");
  await expect(page.locator("pre, code")).toHaveCount(0);
  const id = page.url().split("/").at(-1);
  const stored = await (await page.request.get(`/api/v1/conversations/${id}`)).json();
  await page.getByRole("button", { name: "Copy prompt", exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(stored.card.prompt);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON", exact: true }).click();
  const file = await (await download).path();
  expect(JSON.parse(readFileSync(file!, "utf8"))).toEqual(stored.card.specification);
  await input.press("Shift+Enter");
  await expect(input).toHaveValue("next idea\n");
});
