import { expect, test } from "@playwright/test";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

test("generate one image for the active prompt; edits keep it labelled as an earlier version", async ({ page }) => {
  test.setTimeout(120000);
  let reservations = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/renders")) reservations += 1; });
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
  expect(reservations).toBe(0);
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await input.fill("drafting while the image works");  // image work never blocks the composer
  const image = page.getByRole("img", { name: "Generated image for prompt version 1" });
  await expect(image).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "Generate image", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(image).toBeVisible();
  expect(reservations).toBe(1);
  await input.fill("as a charcoal sketch");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("charcoal sketch", { timeout: 60000 });
  await expect(page.getByText("From earlier prompt version 1")).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate image", exact: true })).toBeVisible();
  expect(reservations).toBe(1);
  const id = page.url().split("/").at(-1);
  const renders = await (await page.request.get(`/api/v1/conversations/${id}/renders`)).json();
  expect(renders.items).toHaveLength(1);
});
