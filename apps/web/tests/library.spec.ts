import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync, rmSync } from "node:fs";

test.describe("real library", () => {
  test.skip(process.env.VISION_TEST_LIBRARY !== "1", "Requires the isolated API/Redis/worker harness");
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Username").fill("transport_reader");
    await page.getByLabel("Password", { exact: true }).fill("synthetic session transport passphrase");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
  });

  test("upload survives reload and parsing is distinct from extraction and indexing", async ({ page }) => {
    await expect(page.getByText("Upload your first book to begin.")).toBeVisible();
    const title = "Élodie 🦊 " + "A long private book title ".repeat(8);
    await page.getByRole("textbox", { name: "Book title", exact: true }).fill(title);
    await page.getByRole("combobox", { name: "Format", exact: true }).selectOption("md");
    const source = readFileSync("../api/tests/fixtures/narrative/story.md");
    await page.getByLabel("Source file").setInputFiles({ name: "story.md", mimeType: "text/markdown", buffer: source });
    const accepted = page.waitForResponse(response => response.url().endsWith("/api/v1/works") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Upload book", exact: true }).click();
    const result = await (await accepted).json();
    const book = page.getByRole("article", { name: title });
    await expect(book.locator(".readiness > div").nth(0)).toContainText("Complete", { timeout: 30000 });
    await expect(book.locator(".readiness > div").nth(1)).toContainText("Waiting for worker");
    await expect(book.locator(".readiness > div").nth(2)).toContainText("Not ready");
    expect(await (await page.request.get(`/api/v1/works/${result.work.id}/original`)).body()).toEqual(source);
    await page.reload();
    await expect(book).toBeVisible();
    for (const theme of ["light", "dark"]) {
      await page.getByRole("button", { name: `Switch to ${theme} mode`, exact: true }).click();
      for (const width of [320, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        if (width === 320) await page.screenshot({ path: `../../.local/library-${theme}-narrow.png`, fullPage: true });
      }
      await page.screenshot({ path: `../../.local/library-${theme}.png`, fullPage: true });
    }
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(book).toHaveCount(0);
    await page.getByLabel("Username").fill("other_reader");
    await page.getByLabel("Password", { exact: true }).fill("synthetic session transport passphrase");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Upload your first book to begin.")).toBeVisible();
    const endpoint = `/api/v1/works/${result.work.id}/ingestions/${result.job.id}`;
    expect((await page.request.get(endpoint)).status()).toBe(404);
    expect((await page.request.post(endpoint + "/cancel", { headers: { Origin: "http://127.0.0.1:13000", "Idempotency-Key": "outsider", "If-Match": '"1"' } })).status()).toBe(404);
  });

  test("queued cancellation, retry, stale revision and malformed-source failure", async ({ page }) => {
    test.setTimeout(90000);
    const pid = Number(process.env.VISION_TEST_WORKER_PID);
    process.kill(-pid, "SIGSTOP");
    let workId = "", jobId = "";
    try {
      await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Cancel and retry");
      await page.getByLabel("Source file").setInputFiles({ name: "book.txt", mimeType: "text/plain", buffer: Buffer.from("Chapter 1\n\nÉlodie wore a blue coat. 🦊") });
      const response = page.waitForResponse(r => r.url().endsWith("/api/v1/works") && r.request().method() === "POST");
      await page.getByRole("button", { name: "Upload book", exact: true }).click();
      const result = await (await response).json();
      workId = result.work.id; jobId = result.job.id;
      const book = page.getByRole("article", { name: "Cancel and retry" });
      const endpoint = `/api/v1/works/${workId}/ingestions/${jobId}`;
      await expect(book.getByRole("button", { name: "Cancel parsing" })).toBeEnabled();
      const stale = await (await page.request.get(endpoint)).json();
      // Another tab commits first; retain the stale state in this view.
      await page.route(`**${endpoint}`, route => route.fulfill({ json: stale }));
      expect((await page.request.post(endpoint + "/cancel", { headers: { Origin: "http://127.0.0.1:13000", "Idempotency-Key": "other-tab", "If-Match": `"${stale.revision}"` } })).status()).toBe(200);
      await book.getByRole("button", { name: "Cancel parsing" }).click();
      await expect(book.getByRole("alert")).toContainText("Processing changed");
      await page.unroute(`**${endpoint}`);
      await expect(book.locator(".readiness > div").nth(0)).toContainText("Cancelled", { timeout: 10000 });
      await book.getByRole("button", { name: "Retry parsing" }).click();
      await expect(book.locator(".readiness > div").nth(0)).toContainText("Waiting for worker");
    } finally { process.kill(-pid, "SIGCONT"); }
    const book = page.getByRole("article", { name: "Cancel and retry" });
    await expect(book.locator(".readiness > div").nth(0)).toContainText("Complete", { timeout: 30000 });
    await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Malformed PDF");
    await page.getByRole("combobox", { name: "Format", exact: true }).selectOption("pdf");
    await page.getByLabel("Source file").setInputFiles({ name: "broken.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7\nmalformed") });
    await page.getByRole("button", { name: "Upload book", exact: true }).click();
    const failed = page.getByRole("article", { name: "Malformed PDF" });
    await expect(failed.locator(".readiness > div").nth(0)).toContainText("Failed", { timeout: 30000 });
    const retried = page.waitForResponse(r => r.url().endsWith("/retry") && r.request().method() === "POST");
    await failed.getByRole("button", { name: "Retry parsing" }).click();
    const retryResponse = await retried;
    expect(retryResponse.status()).toBe(200);
    await expect.poll(async () => {
      const job = await (await page.request.get(retryResponse.url().replace(/\/retry$/, ""))).json();
      return { status: job.status, attempts: job.attempts };
    }, { timeout: 30000 }).toEqual({ status: "failed", attempts: 2 });
    await expect(failed.locator(".readiness > div").nth(0)).toContainText("Failed", { timeout: 30000 });
    expect((await page.request.get(`/api/v1/works/${workId}/ingestions/${jobId}`)).status()).toBe(200);
  });

  test("running cancellation stays pending until the real worker confirms it", async ({ page }) => {
    const gate = process.env.VISION_TEST_PARSE_GATE!;
    writeFileSync(gate, "hold synthetic parser");
    const book = page.getByRole("article", { name: "Slow parsing" });
    try {
      await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Slow parsing");
      await page.getByLabel("Source file").setInputFiles({ name: "slow.txt", mimeType: "text/plain", buffer: Buffer.from("Chapter 1\n\nArthur wore a blue coat.") });
      await page.getByRole("button", { name: "Upload book", exact: true }).click();
      await expect(book.locator(".readiness > div").nth(0)).toContainText("Parsing…", { timeout: 10000 });
      await book.getByRole("button", { name: "Cancel parsing" }).click();
      await expect(book).toContainText("Cancellation requested — waiting for worker");
      await expect(book.getByRole("button", { name: "Cancel parsing" })).toBeDisabled();
      await page.screenshot({ path: "../../.local/library-cancel-pending.png", fullPage: true });
    } finally { rmSync(gate, { force: true }); }
    await expect(book.locator(".readiness > div").nth(0)).toContainText("Cancelled", { timeout: 10000 });
    await expect(book.getByRole("button", { name: "Retry parsing" })).toBeEnabled();
  });

  test("accepted deletion disappears after reload and the worker completes physical cleanup", async ({ page }) => {
    await page.getByRole("textbox", { name: "Book title", exact: true }).fill("Deletion sample");
    await page.getByLabel("Source file").setInputFiles({ name: "delete.txt", mimeType: "text/plain", buffer: Buffer.from("Chapter 1\n\nA temporary synthetic book.") });
    const accepted = page.waitForResponse(r => r.url().endsWith("/api/v1/works") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Upload book", exact: true }).click();
    const response = await accepted;
    expect(response.status()).toBe(202);
    const result = await response.json();
    const book = page.getByRole("article", { name: "Deletion sample" });
    await expect(book).toBeVisible();
    const endpoint = `/api/v1/works/${result.work.id}`;
    const current = await page.request.get(endpoint);
    const headers = { Origin: "http://127.0.0.1:13000", "Idempotency-Key": "browser-deletion", "If-Match": current.headers()["etag"] };
    expect((await page.request.delete(endpoint, { headers })).status()).toBe(202);
    await page.reload();
    await expect(book).toHaveCount(0);
    expect((await page.request.get(endpoint + "/original")).status()).toBe(404);
    await expect.poll(async () => (await (await page.request.delete(endpoint, { headers })).json()).status).toBe("completed");
    await expect(page.getByRole("article", { name: "Cancel and retry" })).toBeVisible();
  });
});

test("private library asks the reader to sign in", async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => route.fulfill({ status: 401, json: { error: { code: "AUTHENTICATION_REQUIRED", message: "Sign in required." } } }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to your library" })).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("type", "password");
});
