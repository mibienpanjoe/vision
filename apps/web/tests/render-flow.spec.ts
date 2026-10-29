import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { chooseArthur, signIn, uploadCorpus } from "./fixtures";

// Billed: exactly two image requests to the configured provider (DEC-51 acceptance budget).
// VISION_TEST_LIVE_RENDER=synthetic rehearses the same flow with the fixture adapter first.
const mode = process.env.VISION_TEST_LIVE_RENDER;
test.skip(mode !== "1" && mode !== "synthetic", "Set VISION_TEST_LIVE_RENDER=1 for two billed image requests");
const OUT = "../../.local/measurements";

async function finished(page: Page, revision: number) {
  const article = page.getByRole("region", { name: "Rendered images" }).getByRole("article", { name: `Render of revision ${revision}` });
  await expect(article).toContainText(/Finished|provider|unknown|could not/, { timeout: 180000 });
  await expect(article, await article.innerText()).toContainText("Finished");
  const href = await article.getByRole("link", { name: "Download image" }).getAttribute("href");
  const image = await page.request.get(href!);
  expect(image.status()).toBe(200);
  writeFileSync(`${OUT}/render-flow-${mode}-r${revision}.png`, await image.body());
  await expect(article.getByRole("img")).toBeVisible();
  expect(await article.getByRole("img").evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(mode === "1" ? 1024 : 8);
  return { article, href: href! };
}

test("live provider renders a stored specification and a locked creative refinement", async ({ page, browser }) => {
  test.setTimeout(480000);
  mkdirSync(OUT, { recursive: true });
  await signIn(page);
  const workId = await uploadCorpus(page, "Live render");
  await chooseArthur(page);
  if (!await page.getByLabel("Story moment", { exact: true }).isVisible()) await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  if (!await page.getByLabel("Story moment", { exact: true }).isVisible()) await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  const created = page.waitForResponse(r => /\/visualizations$/.test(r.url()) && r.request().method() === "POST");
  await page.getByRole("button", { name: "Create visual specification", exact: true }).click();
  const visualization = (await (await created).json()).visualization;
  const renders = page.getByRole("region", { name: "Rendered images" });

  const posted = page.waitForRequest(r => /\/renders$/.test(r.url()) && r.method() === "POST");
  await renders.getByRole("button", { name: "Render revision 1", exact: true }).click();
  const request = await posted;
  const first = await finished(page, 1);

  // Replaying the exact request returns the same job instead of reserving another billed call.
  const replay = await page.request.post(request.url(), { data: request.postDataJSON(), headers: {
    "Content-Type": "application/json", Origin: new URL(page.url()).origin,
    "Idempotency-Key": request.headers()["idempotency-key"] } });
  expect(replay.status()).toBe(202);

  await page.getByLabel("Refinement style", { exact: true }).fill("ink wash");
  await page.getByRole("combobox", { name: "Refinement creative mode", exact: true }).selectOption("interpretation");
  for (const lock of [/Lock Arthur attire/, /Lock Arthur left_cheek/, /Lock Mira held_object/, /Lock house by the ash tree roof/]) {
    await page.getByRole("checkbox", { name: lock }).check();
  }
  await page.getByRole("button", { name: "Save new revision", exact: true }).click();
  await expect(page.getByRole("region", { name: "Visual specification", exact: true })).toContainText("revision 2");
  await renders.getByRole("button", { name: "Render revision 2", exact: true }).click();
  await finished(page, 2);
  await expect(first.article).toContainText("Older specification; the current revision is 2");

  const history = await (await page.request.get(`/api/v1/works/${workId}/visualizations/${visualization.id}/renders`)).json();
  expect(history.items).toHaveLength(2);
  expect((await replay.json()).id).toBe(history.items[1].id);
  const anonymous = await browser.newContext();
  expect((await anonymous.request.get(new URL(first.href, page.url()).toString())).status()).toBe(401);
  await anonymous.close();

  const revisions = await Promise.all([1, 2].map(async number => (await (await page.request.get(
    `/api/v1/works/${workId}/visualizations/${visualization.id}/revisions/${number}`)).json()).result.data));
  writeFileSync(`${OUT}/render-flow-${mode}.json`, JSON.stringify({
    renders: history.items, prompts: revisions.map(spec => spec.generation), locks: revisions[1].locks }, null, 2));
  await page.screenshot({ path: `../../.local/render-flow-${mode}.png`, fullPage: true });
});
