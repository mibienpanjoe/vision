import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

export async function signIn(page: Page, username = "transport_reader", password = "synthetic session transport passphrase") {
  const result = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: "http://127.0.0.1:13000" },
    data: { username, password },
  });
  expect(result.status()).toBe(200);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your books" })).toBeVisible();
}

export async function uploadCorpus(page: Page, title: string) {
  await page.getByRole("textbox", { name: "Book title", exact: true }).fill(title);
  await page.getByRole("combobox", { name: "Format", exact: true }).selectOption("md");
  await page.getByLabel("Source file").setInputFiles({ name: "story.md", mimeType: "text/markdown", buffer: readFileSync("../api/tests/fixtures/narrative/story.md") });
  const accepted = page.waitForResponse(response => response.url().endsWith("/api/v1/works") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Upload book", exact: true }).click();
  const record = await (await accepted).json();
  const book = page.getByRole("article", { name: title, exact: true });
  await expect(book.locator(".readiness > div").nth(2)).toContainText("Ready", { timeout: 120000 });
  await book.getByRole("link", { name: "Open book" }).click();
  return record.work.id as string;
}

export async function chooseArthur(page: Page, chapter = 3) {
  await page.getByRole("combobox", { name: "Reading boundary", exact: true }).selectOption({ label: `Through chapter ${chapter}` });
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
}
