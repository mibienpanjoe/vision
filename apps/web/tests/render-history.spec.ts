import { expect, test } from "@playwright/test";
import { chooseArthur, signIn, uploadCorpus } from "./fixtures";

test.skip(process.env.VISION_TEST_WORKSPACE !== "1", "Requires isolated workspace API/worker fixtures");
test("a real worker's render is private, downloadable and reopens its exact specification revision", async ({ page, browser }) => {
  test.setTimeout(120000);
  await signIn(page);
  await uploadCorpus(page, "Render history");
  await chooseArthur(page);
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  await page.getByRole("button", { name: "Create visual specification", exact: true }).click();
  const renders = page.getByRole("region", { name: "Rendered images" });
  await expect(renders).toContainText("No rendered images for this specification yet.");
  await renders.getByRole("button", { name: "Render revision 1", exact: true }).click();
  const first = renders.getByRole("article", { name: "Render of revision 1" });
  await expect(first).toContainText("Finished", { timeout: 30000 });
  const image = first.getByRole("img", { name: "Generated image of revision 1" });
  await expect(image).toBeVisible();
  expect(await image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth)).toBe(8);
  await expect(first).toContainText("not evidence");

  const href = await first.getByRole("link", { name: "Download image" }).getAttribute("href");
  const download = await page.request.get(href!);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-type"]).toBe("image/png");
  expect(download.headers()["content-disposition"]).toMatch(/^attachment; filename="vision-render-[0-9a-f]{12}\.png"$/);
  const anonymous = await browser.newContext();
  expect((await anonymous.request.get(new URL(href!, page.url()).toString())).status()).toBe(401);
  await anonymous.close();

  await page.getByLabel("Refinement style", { exact: true }).fill("charcoal");
  await page.getByRole("button", { name: "Save new revision", exact: true }).click();
  const profile = page.getByRole("region", { name: "Visual specification", exact: true });
  await expect(profile).toContainText("revision 2");
  await expect(first).toContainText("Older specification; the current revision is 2");
  await expect(renders.getByRole("button", { name: "Render revision 2", exact: true })).toBeVisible();
  await page.screenshot({ path: "../../.local/render-history.png", fullPage: true });

  await first.getByRole("button", { name: "Show revision 1", exact: true }).click();
  await expect(profile).toContainText("revision 1");
  await expect(page.getByText("Historical revision.")).toBeVisible();
  await expect(renders.getByRole("button", { name: /Render revision/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Refine presentation" })).toHaveCount(0);
});
