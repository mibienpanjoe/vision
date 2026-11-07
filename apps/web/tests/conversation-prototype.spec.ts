import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/preview/conversation");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
}

async function ask(page: Page) {
  await page.getByRole("button", { name: "Try the sample book" }).click();
  await page.getByRole("textbox", { name: "Your message" }).fill("Show Arthur before the war");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("heading", { name: "Your image prompt" })).toBeVisible();
}

async function outcome(page: Page, value: string) {
  await page.getByText("Preview controls", { exact: true }).click();
  await page.getByLabel("Next sample outcome").selectOption(value);
  await page.getByText("Preview controls", { exact: true }).click();
}

test("attach and ask, moments, exact copy, source focus and revision-bound sample image", async ({ page, context }) => {
  const api: string[] = [];
  page.on("request", request => { if (/\/api\/|\/v1\//.test(request.url())) api.push(request.url()); });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await open(page);
  await expect(page.getByRole("textbox", { name: /username|password/i })).toHaveCount(0);
  await page.getByLabel("Attach book").setInputFiles({ name: "The House by the Ash Tree.md", mimeType: "text/markdown", buffer: Buffer.from("sample") });
  await expect(page.getByText("The House by the Ash Tree · MD", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Your message" }).fill("Show Arthur before the war");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("status")).toContainText("Reading the sample book");
  await page.getByRole("textbox", { name: "Your message" }).fill("Keep the clothes");
  await expect(page.getByRole("heading", { name: "Your image prompt" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your message" })).toHaveValue("Keep the clothes");
  const prompt = page.getByTestId("active-prompt");
  await expect(prompt).toContainText("blue wool coat");
  await expect(prompt).not.toContainText(/golden eyes|steel armor/);
  await page.getByRole("button", { name: "Copy prompt", exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await prompt.innerText());
  const source = page.getByRole("button", { name: "Sources", exact: true });
  await source.click();
  await expect(page.getByRole("dialog")).toContainText("At ten, Arthur had chestnut hair");
  await expect(page.getByRole("dialog").locator("mark")).toHaveText("blue wool coat");
  await page.keyboard.press("Escape");
  await expect(source).toBeFocused();
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.getByText("Sample image · prompt version 1", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download sample image" }).click();
  expect((await download).suggestedFilename()).toBe("sample-prompt-1.svg");
  await page.getByRole("button", { name: /At home.*Linen shirt/ }).click();
  await expect(prompt).toContainText("linen shirt");
  await expect(page.getByText("Sample image · prompt version 1", { exact: true })).toBeVisible();
  await expect(page.getByText("From an earlier prompt version")).toBeVisible();
  await expect(page.getByRole("button", { name: /At home.*Linen shirt/ })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("textbox", { name: "Your message" }).fill("Make it charcoal");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(prompt).toContainText("Charcoal");
  await expect(prompt).toContainText("linen shirt");
  await page.reload();
  await expect(prompt).toContainText("Charcoal");
  await expect(page.getByText("Sample image · prompt version 1", { exact: true })).toBeVisible();
  expect(api).toEqual([]);
});

test("preparation failure, ambiguity, missing evidence and provider failure have distinct recovery", async ({ page }) => {
  await open(page);
  await outcome(page, "preparation-error");
  await page.getByRole("button", { name: "Try the sample book" }).click();
  const draft = page.getByRole("textbox", { name: "Your message" });
  await draft.fill("Describe Arthur");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("could not be read");
  await expect(page.getByText("Describe Arthur", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry preparation" }).click();
  await expect(page.getByTestId("active-prompt")).toBeVisible();
  await outcome(page, "ambiguity");
  await draft.fill("Describe the captain");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Which captain do you mean?", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mira · brass compass" }).click();
  await expect(page.getByTestId("active-prompt")).toContainText("Mira");
  await outcome(page, "missing-evidence");
  await draft.fill("Describe the messenger");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("status")).toContainText("No supported appearance");
  await expect(page.getByTestId("active-prompt")).toContainText("Mira");
  await outcome(page, "provider-error");
  await draft.fill("Try another view");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("service is unavailable");
  await expect(page.getByTestId("active-prompt")).toContainText("Mira");
  await page.getByRole("button", { name: "Retry response" }).click();
  await expect(page.getByRole("status")).toContainText("updated");
});

test("stale revision and uncertain paid outcome preserve prior work without an automatic send", async ({ page }) => {
  await open(page);
  await ask(page);
  await outcome(page, "stale");
  await page.getByRole("button", { name: /At home.*Linen shirt/ }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("changed in another tab");
  await expect(page.getByTestId("active-prompt")).toContainText("blue wool coat");
  await page.getByRole("button", { name: "Refresh current version" }).click();
  await outcome(page, "image-unknown");
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Acceptance unknown");
  await expect(page.getByRole("button", { name: "Generate image", exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.locator("main").getByRole("alert")).toContainText("Acceptance unknown");
  await expect(page.getByRole("button", { name: "Generate image", exact: true })).toBeDisabled();
});

test("history, versions and export retain the active card while updates preserve reading position", async ({ page }) => {
  await open(page);
  await ask(page);
  for (let index = 0; index < 4; index++) {
    await page.getByRole("textbox", { name: "Your message" }).fill(`Make it charcoal ${index}`);
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByText(`Version ${index + 2}`, { exact: true })).toBeVisible();
  }
  const before = await page.getByTestId("active-prompt").innerText();
  await page.getByRole("button", { name: "Versions & export" }).click();
  await page.getByRole("button", { name: "Version 1", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Historical version · active prompt unchanged");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export current sample JSON" }).click();
  const file = await (await download).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of file!) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString()).revision.prompt).toBe(before);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("active-prompt")).toHaveText(before);
  await page.getByRole("textbox", { name: "Your message" }).fill("Keep the clothes");
  await page.getByRole("button", { name: "Send message" }).click();
  const thread = page.locator(".conversation-thread");
  await thread.evaluate(element => { element.scrollTop = 0; });
  await expect(page.locator("main").getByText("Version 6", { exact: true })).toBeAttached();
  expect(await thread.evaluate(element => element.scrollTop)).toBe(0);
  await expect(page.getByRole("button", { name: "Return to latest" })).toBeVisible();
  await page.getByRole("button", { name: "Return to latest" }).click();
  expect(await thread.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByTestId("active-prompt")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: /The House by the Ash Tree.*Arthur’s appearance/ }).click();
  await expect(page.locator("main").getByText("Version 6", { exact: true })).toBeVisible();
});

test("book replacement resumes the waiting question; storage and rejected image states recover", async ({ page }) => {
  await open(page);
  await outcome(page, "storage-error");
  await expect(page.locator("main").getByRole("alert")).toContainText("storage is unavailable");
  await page.getByRole("textbox", { name: "Your message" }).fill("Show Arthur before the war");
  await page.getByRole("button", { name: "Retry storage" }).click();
  await outcome(page, "preparation-error");
  await page.getByRole("button", { name: "Try the sample book" }).click();
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("could not be read");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Replace book" }).click();
  await (await chooser).setFiles({ name: "Replacement.md", mimeType: "text/markdown", buffer: Buffer.from("sample") });
  await expect(page.getByTestId("active-prompt")).toContainText("blue wool coat");
  await expect(page.getByText("Show Arthur before the war", { exact: true })).toHaveCount(1);
  await outcome(page, "image-error");
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("rejected before acceptance");
  await outcome(page, "ready");
  await page.getByRole("button", { name: "Generate image", exact: true }).click();
  await expect(page.getByText("Sample image · prompt version 1", { exact: true })).toBeVisible();
});

for (const size of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 720 }]) {
  test(`populated and failed layouts at ${size.width}px, keyboard, themes and large text`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (["error", "warning"].includes(message.type())) errors.push(message.text()); });
    await page.setViewportSize(size);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await open(page);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to conversation" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("main")).toBeFocused();
    await ask(page);
    for (const theme of ["light", "dark"]) {
      const toggle = page.getByRole("button", { name: `Switch to ${theme} mode` });
      if (await toggle.count()) await toggle.click();
      await expect(page.locator("html")).toHaveClass(theme);
      await page.getByRole("button", { name: /At home.*Linen shirt/ }).scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: `../../.local/q27/${size.width}-${theme}-ready.png`, fullPage: true });
    }
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await outcome(page, "provider-error");
    await page.getByRole("textbox", { name: "Your message" }).fill("A very long request about Arthur's appearance and the remembered clothes in this story".repeat(3));
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
    expect(await page.getByRole("textbox", { name: "Your message" }).evaluate(element => element.scrollTop)).toBe(0);
    await page.locator("main").getByRole("alert").scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../../.local/q27/${size.width}-large-error.png`, fullPage: true });
    expect(errors).toEqual([]);
  });
}
