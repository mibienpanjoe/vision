import { expect, type Page } from "@playwright/test";

export async function signIn(page: Page, username = "transport_reader", password = "synthetic session transport passphrase") {
  const result = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: "http://127.0.0.1:13000" },
    data: { username, password },
  });
  expect(result.status()).toBe(200);
  await page.goto("/conversations/new");
  await expect(page.getByRole("heading", { name: "What would you like to see?" })).toBeVisible();
}
