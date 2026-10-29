import { expect, test } from "@playwright/test";
import { chooseArthur, signIn, uploadCorpus } from "./fixtures";

test.skip(process.env.VISION_TEST_WORKSPACE !== "1", "Requires isolated workspace fixtures");
test("populated workspace retains labels, contrast, keyboard access and layout at large text sizes", async ({ page }) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page);
  await expect(page.getByText("Upload your first book to begin.")).toBeVisible();
  await uploadCorpus(page, "Accessibility review — a world with dense evidence and unknown details");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to book", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await chooseArthur(page);
  if (!await page.getByLabel("Story moment", { exact: true }).isVisible()) await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("Story moment", { exact: true }).fill("after the war");
  if (!await page.getByLabel("Story moment", { exact: true }).isVisible()) await page.getByText("More options", { exact: true }).click();
  await page.getByLabel("Scene context", { exact: true }).fill("at home");
  await page.getByRole("button", { name: "Create visual specification", exact: true }).click();
  const profile = page.getByRole("region", { name: "Visual specification", exact: true });
  await expect(profile).toContainText("Canonical");
  await profile.getByRole("button", { name: /Arthur · attire:/ }).click();
  await expect(profile.getByRole("region", { name: "Source reader" }).locator('mark[data-selected="true"]')).toBeVisible();
  for (const theme of ["light", "dark"]) {
    await page.getByRole("button", { name: `Switch to ${theme} mode`, exact: true }).click();
    const contrast = await page.evaluate(() => {
      function rgb(color: string) { return (color.match(/[\d.]+/g) ?? []).map(Number); }
      function luminance(color: number[]) {
        const channels = color.slice(0, 3).map(channel => { const value = channel / 255; return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4; });
        return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
      }
      const failures: string[] = [];
      for (const element of document.querySelectorAll<HTMLElement>("p, label, button, a, select, input, textarea, summary, h1, h2, h3, h4")) {
        if (!element.getClientRects().length || element.closest("[disabled]")) continue;
        const style = getComputedStyle(element);
        if (style.visibility === "hidden") continue;
        let parent: HTMLElement | null = element;
        let background: number[] = [];
        while (parent) {
          const value = rgb(getComputedStyle(parent).backgroundColor);
          if (value.length === 3 || value[3] === 1) { background = value; break; }
          parent = parent.parentElement;
        }
        if (!background.length) continue;
        const a = luminance(rgb(style.color)), b = luminance(background);
        const ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
        const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && parseInt(style.fontWeight) >= 700);
        if (ratio < (large ? 3 : 4.5)) failures.push(`${element.tagName}: ${ratio.toFixed(2)}`);
        if ((element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) && element.placeholder) {
          const placeholder = luminance(rgb(getComputedStyle(element, "::placeholder").color));
          const placeholderRatio = (Math.max(placeholder, b) + .05) / (Math.min(placeholder, b) + .05);
          if (placeholderRatio < 4.5) failures.push(`placeholder: ${placeholderRatio.toFixed(2)}`);
        }
      }
      return failures;
    });
    expect(contrast, theme).toEqual([]);
    await page.screenshot({ path: `../../.local/workspace-${theme}-populated.png`, fullPage: true });
    for (const width of [320, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${theme} ${width}`).toBe(true);
    }
    await page.setViewportSize({ width: 320, height: 900 });
    await page.addStyleTag({ content: "html { font-size: 200%; }" });
    const overflow = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("body *")].filter(element => element.getBoundingClientRect().right > innerWidth + 1).map(element => `${element.tagName}.${element.className}`).slice(0, 20));
    expect(overflow, `${theme} 200% text`).toEqual([]);
    await page.getByRole("group", { name: "Workspace view", exact: true }).getByRole("button", { name: "Evidence", exact: true }).click();
    const reader = profile.getByRole("region", { name: "Source reader" });
    await reader.scrollIntoViewIfNeeded();
    expect(await reader.locator(".source-excerpt").evaluate(element => element.getBoundingClientRect().width)).toBeGreaterThan(180);
    await page.screenshot({ path: `../../.local/workspace-${theme}-large-text.png` });
    await page.addStyleTag({ content: "html { font-size: 100%; }" });
  }
  const structure = await page.evaluate(() => {
    const headings = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].map(heading => Number(heading.tagName[1]));
    const unnamed = [...document.querySelectorAll<HTMLElement>("button,input,textarea,select")].filter(element => {
      const labels = element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement ? element.labels : null;
      return !element.getAttribute("aria-label") && !element.textContent?.trim() && !labels?.length;
    });
    const ids = [...document.querySelectorAll("[id]")].map(element => element.id);
    return { titles: headings.filter(level => level === 1).length, skipped: headings.some((level, index) => index > 0 && level > headings[index - 1] + 1), unnamed: unnamed.length, duplicateIds: ids.length !== new Set(ids).size };
  });
  expect(structure).toEqual({ titles: 1, skipped: false, unnamed: 0, duplicateIds: false });
  expect(errors).toEqual([]);
});
