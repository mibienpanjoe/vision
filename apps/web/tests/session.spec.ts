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
  expect((await page.request.post("/api/v1/auth/logout", { headers: { Origin: baseURL! } })).status()).toBe(204);
  expect((await page.goto("/api/v1/auth/me"))?.status()).toBe(401);
});
