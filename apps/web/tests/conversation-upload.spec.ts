import { expect, test } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";

test.skip(process.env.VISION_TEST_CONVERSATION !== "1", "Requires isolated conversation API/parser/worker services");

test("attach and ask in one composer, receive the stored prompt and reopen without another upload", async ({ page }) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", item => { if (item.type() === "error") errors.push(item.text()); });
  let uploads = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().endsWith("/api/v1/works")) uploads += 1; });
  await page.goto("/conversations/new");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
  await expect(page.getByLabel("Username")).toHaveCount(0);
  await expect(page.getByLabel("Book title", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Reading boundary", { exact: true })).toHaveCount(0);
  const source = readFileSync("../api/tests/fixtures/narrative/story.md");
  await page.getByLabel("Book file").setInputFiles({ name: "story.md", mimeType: "text/markdown", buffer: source });
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  const uploaded = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/api/v1/works"));
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const book = (await (await uploaded).json()).work;
  await expect(page).toHaveURL(/\/conversations\/[0-9a-f-]{36}$/);
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  const id = page.url().split("/").at(-1);
  const stored = await (await page.request.get(`/api/v1/conversations/${id}`)).json();
  await expect(prompt).toHaveText(stored.card.specification.result.data.generation.prompt);
  expect(await (await page.request.get(`/api/v1/works/${book.id}/original`)).body()).toEqual(source);
  await page.reload();
  await expect(prompt).toHaveText(stored.card.prompt);
  expect(uploads).toBe(1);
  mkdirSync("../../.local/q37d", { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../../.local/q37d/conversation-${width}.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
  await expect(page.getByRole("list", { name: "Conversation messages" }).getByText("Arthur after the war at home", { exact: true })).toBeVisible();
});


test("file-only attachment and later question reuse one original", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page).toHaveURL(/\/conversations\/[0-9a-f-]{36}$/);
  await expect(page.getByText("Book ready", { exact: true })).toBeVisible({ timeout: 60000 });
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 30000 });
  const books = await (await page.request.get("/api/v1/works")).json();
  expect(books.items).toHaveLength(1);
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("button", { name: "Copy prompt", exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await page.getByTestId("active-prompt").textContent());
});

test("typing during an upload is preserved while the captured question finishes", async ({ page }) => {
  test.setTimeout(90000);
  let release: () => void = () => {};
  let received: () => void = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  const captured = new Promise<void>(resolve => { received = resolve; });
  await page.route("**/api/v1/works", async route => {
    if (route.request().method() !== "POST") return route.continue();
    received(); await held; await route.continue();
  });
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  try {
    await captured;
    await input.fill("A draft for my next question");
  } finally { release(); }
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
  await expect(input).toHaveValue("A draft for my next question");
});

test("a lost upload response retries the same receipt without a second book", async ({ page }) => {
  test.setTimeout(90000);
  let lost = false;
  let originalId = "";
  await page.route("**/api/v1/works", async route => {
    if (route.request().method() !== "POST" || lost) return route.continue();
    lost = true;
    const accepted = await page.request.post(route.request().url(), {
      headers: { Origin: "http://127.0.0.1:13000", "Idempotency-Key": route.request().headers()["idempotency-key"] },
      multipart: { file: { name: "story.md", mimeType: "text/markdown", buffer: readFileSync("../api/tests/fixtures/narrative/story.md") } },
    });
    expect(accepted.status()).toBe(202);
    originalId = (await accepted.json()).work.id;
    await route.abort("failed");
  });
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Retry request", exact: true }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
  const books = (await (await page.request.get("/api/v1/works")).json()).items;
  expect(books.map((book: { id: string }) => book.id)).toEqual([originalId]);
  const id = page.url().split("/").at(-1);
  const messages = await (await page.request.get(`/api/v1/conversations/${id}/messages`)).json();
  expect(messages.items.filter((item: { role: string }) => item.role === "user")).toHaveLength(1);
});

for (const [name, mimeType] of [["story.txt", "text/plain"], ["story.pdf", "application/pdf"], ["story.epub", "application/epub+zip"]]) {
  test(`attach and ask with a ${name.split(".")[1].toUpperCase()} book`, async ({ page }) => {
    test.setTimeout(90000);
    let buffer: Buffer;
    if (name.endsWith(".txt")) buffer = readFileSync("../api/tests/fixtures/narrative/story.md");
    else if (name.endsWith(".pdf")) buffer = readFileSync("../api/tests/fixtures/formats/story.pdf");
    else buffer = execFileSync("./.venv/bin/python", ["-c", "import sys; from tests.epub_builder import build; sys.stdout.buffer.write(build())"], { cwd: "../api" });
    await page.goto("/conversations/new");
    await page.getByLabel("Book file").setInputFiles({ name, mimeType, buffer });
    await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByTestId("active-prompt")).toContainText("plain linen shirt", { timeout: 60000 });
  });
}

test("a scanned PDF keeps the question and explains what to attach instead", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/formats/outlined.pdf");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("This PDF has no extractable text. Attach a text PDF, EPUB or text file.")).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("list", { name: "Conversation messages" }).getByText("Arthur after the war at home", { exact: true })).toBeVisible();
});

test("one click on another moment replaces the prompt with a verified portrayal", async ({ page }) => {
  test.setTimeout(90000);
  let renders = 0;
  page.on("request", request => { if (request.method() === "POST" && /renders|images/.test(request.url())) renders += 1; });
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  await page.getByRole("group", { name: "Other moments" }).getByRole("button", { name: /^war/ }).click();
  await expect(prompt).toContainText("steel armor", { timeout: 60000 });
  await expect(page.getByRole("list", { name: "Conversation messages" }).getByText("Show war", { exact: true })).toBeVisible();
  expect(renders).toBe(0);
});

test("a second tab cannot silently apply a stale edit and earlier versions stay historical", async ({ page, context }) => {
  test.setTimeout(120000);
  await page.goto("/conversations/new");
  await page.getByLabel("Book file").setInputFiles("../api/tests/fixtures/narrative/story.md");
  await page.getByRole("textbox", { name: "Message" }).fill("Arthur after the war at home");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("plain linen shirt", { timeout: 60000 });
  const first = await prompt.textContent();
  const other = await context.newPage();
  await other.goto(page.url());
  await expect(other.getByTestId("active-prompt")).toHaveText(first!);
  await page.getByRole("textbox", { name: "Message" }).fill("as a charcoal sketch");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(prompt).toContainText("charcoal sketch", { timeout: 60000 });
  await other.getByRole("textbox", { name: "Message" }).fill("as an oil painting");
  await other.getByRole("button", { name: "Send", exact: true }).click();
  await expect(other.getByRole("button", { name: "Refresh conversation" })).toBeVisible();
  await expect(other.getByTestId("active-prompt")).toHaveText(first!);
  await page.getByText("Earlier versions").click();
  await expect(page.getByLabel("Earlier version 1")).toContainText(first!);
  await expect(prompt).toContainText("charcoal sketch");
});
