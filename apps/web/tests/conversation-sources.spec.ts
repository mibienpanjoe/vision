import { expect, test } from "@playwright/test";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

test("sources open exact excerpts in a sheet, restore focus and add no chat message", async ({ page, browser }) => {
  test.setTimeout(90000);
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
  const messages = await page.getByRole("list", { name: "Conversation messages" }).locator("li").count();
  await page.evaluate(() => scrollTo(0, 120));
  const before = await page.evaluate(() => scrollY);
  const opener = page.getByRole("button", { name: "Sources", exact: true });
  await opener.press("Enter");
  const sheet = page.getByRole("dialog", { name: "Sources" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("listitem").getByRole("button", { name: /attire: plain linen shirt/ }).click();
  await expect(sheet.locator("mark").filter({ hasText: "plain linen shirt" }).first()).toBeVisible();
  await expect(sheet.locator("mark[data-selected=true]")).toContainText("plain linen shirt");
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(opener).toBeFocused();
  expect(await page.evaluate(() => scrollY)).toBe(before);
  await expect(page.getByRole("list", { name: "Conversation messages" }).locator("li")).toHaveCount(messages);
  // Another owner cannot read the excerpt behind the same span.
  const id = page.url().split("/").at(-1);
  const stored = await (await page.request.get(`/api/v1/conversations/${id}`)).json();
  const span = stored.card.specification.result.data.subject.traits[0].evidence[0];
  const stranger = await browser.newContext();
  const denied = await stranger.request.post(`/api/v1/works/${stored.work_id}/evidence`, {
    headers: { Origin: "http://127.0.0.1:13000" }, data: { span, parser_revision: stored.card.specification.result.data.scope.parser_revision, reading_boundary: { mode: "whole_book" } } });
  expect([401, 404]).toContain(denied.status());
  await stranger.close();
});
