import { expect, test } from "@playwright/test";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

test("ambiguity offers grounded choices and missing evidence explains itself, keeping the conversation usable", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("the captain during the war");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const choices = page.getByRole("group", { name: "Which did you mean?" });
  await expect(choices.getByRole("button")).toHaveCount(2, { timeout: 60000 });
  await expect(choices).toContainText("Mira");
  await choices.getByRole("button", { name: /Mira/ }).click();
  await expect(page.getByRole("list", { name: "Conversation messages" }).getByText("Captain Mira (character)", { exact: true })).toBeVisible();
  // The answer narrows the subject; the book then offers its grounded moments for Mira.
  await choices.getByRole("button", { name: /^dinner/ }).click({ timeout: 60000 });
  await expect(page.getByTestId("active-prompt")).toContainText("Mira", { timeout: 60000 });
  await expect(choices).toHaveCount(0);
  await input.fill("the dragon");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(/Not established in the book:/)).toBeVisible({ timeout: 60000 });
  await expect(input).toBeEnabled();
});
