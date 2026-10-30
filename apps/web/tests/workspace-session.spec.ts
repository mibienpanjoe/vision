import { expect, test } from "@playwright/test";

test("first visit, reload and concurrent tabs open the same private workspace without credential fields", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your books" })).toBeVisible();
  await expect(page.getByLabel("Username")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);
  const actor = await (await page.request.get("/api/v1/auth/me")).json();
  const other = await context.newPage();
  await Promise.all([other.goto("/"), page.reload()]);
  await expect(other.getByRole("heading", { name: "Your books" })).toBeVisible();
  expect((await (await other.request.get("/api/v1/auth/me")).json()).id).toBe(actor.id);
  await other.close();
});

test("separate browser capabilities cannot claim or read another workspace book", async ({ browser, baseURL }) => {
  const a = await browser.newContext({ baseURL }), b = await browser.newContext({ baseURL });
  try {
    const first = await a.newPage(), second = await b.newPage();
    await Promise.all([first.goto("/"), second.goto("/")]);
    await expect(first.getByRole("heading", { name: "Your books" })).toBeVisible();
    await expect(second.getByRole("heading", { name: "Your books" })).toBeVisible();
    const upload = await a.request.post("/api/v1/works", { headers: { Origin: baseURL!, "Idempotency-Key": "workspace-owned-book" }, multipart: { title: "Private synthetic book", format: "txt", file: { name: "sample.txt", mimeType: "text/plain", buffer: Buffer.from("Lena wore a blue coat.") } } });
    expect(upload.status()).toBe(202);
    const work = (await upload.json()).work;
    expect((await b.request.get(`/api/v1/works/${work.id}`)).status()).toBe(404);
    expect((await b.request.get(`/api/v1/works/${work.id}/original`)).status()).toBe(404);
    expect(await (await b.request.get("/api/v1/works")).json()).toMatchObject({ items: [] });
    const firstActor = (await (await a.request.get("/api/v1/auth/me")).json()).id;
    expect((await (await b.request.get("/api/v1/auth/me")).json()).id).not.toBe(firstActor);
  } finally { await a.close(); await b.close(); }
});

test("cold concurrent tabs serialize initialization without an owner split", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL });
  try {
    const first = await context.newPage(), second = await context.newPage();
    await Promise.all([first.goto("/"), second.goto("/")]);
    await expect(first.getByRole("heading", { name: "Your books" })).toBeVisible();
    await expect(second.getByRole("heading", { name: "Your books" })).toBeVisible();
    expect((await (await first.request.get("/api/v1/auth/me")).json()).id).toBe((await (await second.request.get("/api/v1/auth/me")).json()).id);
  } finally { await context.close(); }
});

test("lost established cookie fails closed instead of recreating an owner or allowance", async ({ page, context, baseURL }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your books" })).toBeVisible();
  expect((await page.request.post("/api/v1/auth/logout", { headers: { Origin: baseURL! } })).status()).toBe(204);
  await context.clearCookies();
  await page.reload();
  await expect(page.locator("main").getByRole("alert")).toContainText("Authentication required.");
  await expect(page.getByLabel("Username")).toHaveCount(0);
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
});
