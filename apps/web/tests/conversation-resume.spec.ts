import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");
const ORIGIN = { Origin: "http://127.0.0.1:13000" };

test("saved books group conversations, reopen without upload, page long histories and stay private", async ({ page, browser }) => {
  test.setTimeout(150000);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.getByRole("img", { name: /prompt version 1/ })).toBeVisible({ timeout: 60000 });
  const first = page.url();
  const view = await (await page.request.get(`/api/v1/conversations/${first.split("/").at(-1)}`)).json();
  // A second book with its own thread.
  const upload = await page.request.post("/api/v1/works", { headers: { ...ORIGIN, "Idempotency-Key": "second-book" },
    multipart: { file: { name: "second.txt", mimeType: "text/plain", buffer: readFileSync("../api/tests/fixtures/narrative/story.md") } } });
  const second = (await upload.json()).work;
  // A long history on the first book.
  for (let index = 0; index < 22; index++) {
    expect((await page.request.post("/api/v1/conversations", { headers: { ...ORIGIN, "Idempotency-Key": `thread-${index}` },
      data: { work_id: view.work_id, title: `Question ${index}` } })).status()).toBe(201);
  }
  await page.request.post("/api/v1/conversations", { headers: { ...ORIGIN, "Idempotency-Key": "second-thread" }, data: { work_id: second.id, title: "Second book question" } });
  await page.goto(first);
  const books = page.getByRole("navigation", { name: "Your books" });
  await expect(books.getByRole("heading", { level: 2 })).toHaveCount(2);
  await expect(books.getByRole("link", { name: "Arthur after the war at home" })).toHaveCount(0);  // beyond the first page
  await books.getByRole("button", { name: "Show more" }).click();
  await expect(books.getByRole("link", { name: "Arthur after the war at home" })).toHaveAttribute("aria-current", "page");
  // Reload restores the active prompt and the completed image with no upload.
  await page.reload();
  await expect(prompt).toHaveText(view.card.prompt);
  await expect(page.getByRole("img", { name: /prompt version 1/ })).toBeVisible();
  await expect(page.getByLabel("Book file")).toHaveCount(0);
  // Ask about a saved book without uploading again.
  await page.goto(`/conversations/new?work=${view.work_id}`);
  await expect(page.getByLabel("Book file")).toHaveCount(0);
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur during the war");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(prompt).toContainText("steel armor", { timeout: 60000 });
  expect((await (await page.request.get("/api/v1/works")).json()).items).toHaveLength(2);
  // Another browser is another private workspace.
  const other = await browser.newContext();
  const stranger = await other.newPage();
  await stranger.goto(first);
  await expect(stranger.getByTestId("active-prompt")).toHaveCount(0);
  await other.close();
});
