import { expect, test } from "@playwright/test";

test("same-origin proxy carries an HttpOnly session to the real API", async ({ page, baseURL }) => {
  test.skip(process.env.VISION_TEST_WEB_SESSION !== "1", "Requires the isolated API session test harness");
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: baseURL! },
    data: { username: "transport_reader", password: "synthetic session transport passphrase" },
  });
  expect(login.status()).toBe(200);
  expect(login.headers()["set-cookie"].toLowerCase()).toContain("httponly");
  expect(login.headers()["set-cookie"].toLowerCase()).toContain("samesite=strict");
  const authenticated = await page.goto("/api/v1/auth/me");
  expect(authenticated?.status()).toBe(200);
  await expect(page.locator("body")).toContainText("transport_reader");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your library", exact: true })).toBeVisible();
  const uploaded = await page.evaluate(async () => {
    const source = "é🦊é\r\nThe captain wore a blue coat.";
    const form = new FormData();
    form.set("title", "Browser synthetic original");
    form.set("format", "txt");
    form.set("file", new File([source], "book.txt", { type: "text/plain" }));
    const response = await fetch("/api/v1/works", {
      method: "POST", headers: { "Idempotency-Key": "browser-source" }, body: form,
    });
    const accepted = await response.json();
    if (response.status !== 202) return { status: response.status };
    const library = await (await fetch("/api/v1/works")).json();
    const original = await (await fetch(`/api/v1/works/${accepted.work.id}/original`)).text();
    return { status: response.status, title: library.items[0].title,
      exactOriginal: original === source, queued: accepted.job.status === "queued" };
  });
  expect(uploaded).toEqual({ status: 202, title: "Browser synthetic original", exactOriginal: true, queued: true });
  expect((await page.request.post("/api/v1/auth/logout", { headers: { Origin: baseURL! } })).status()).toBe(204);
  expect((await page.goto("/api/v1/auth/me"))?.status()).toBe(401);
});
