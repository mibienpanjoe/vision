import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

export async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill("transport_reader");
  await page.getByLabel("Password", { exact: true }).fill("synthetic session transport passphrase");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
}

export async function uploadCorpus(page: Page, title: string) {
  await page.getByRole("textbox", { name: "Book title", exact: true }).fill(title);
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
  if (!await page.locator(".browse-options").evaluate(element => element.hasAttribute("open"))) await page.getByText("Browse people, places and objects", { exact: true }).click();
  await page.getByRole("button", { name: "Arthur", exact: true }).click();
}
