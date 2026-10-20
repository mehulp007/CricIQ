import { expect, test } from "@playwright/test";

// The home page's scroll story. Its numbers and the 2019 final are bundled with the app, so these
// hold on the fixture data in CI as on the full data.

test.describe("landing story", () => {
  test("tells the story in five chapters, ending at the competitions", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: /Decode the game\./ })).toBeVisible();
    await expect(
      page.getByRole("img", { name: /cricket ball.*win-probability ribbon/ }),
    ).toBeAttached();
    for (const name of [
      /Nothing assumed\. Nothing hallucinated\./,
      /Every ball changes the story\./,
      /Every outcome\./,
      "Choose a competition",
    ]) {
      await expect(page.getByRole("heading", { name })).toBeAttached();
    }
    // The counters end on the exact figures (read by screen readers from the start).
    await expect(page.locator("#record").getByText("4,570,681").last()).toBeAttached();
    // The ribbon's moments come from the real balls of the 2019 IPL final.
    const ribbon = page.locator("#ribbon");
    await expect(ribbon.getByText("Pollard's six")).toBeAttached();
    await expect(ribbon.getByText(/CSK need 9 off 6/)).toBeAttached();
  });

  test("the chapters pin, the counter runs and the ribbon's moments arrive", async ({ page }) => {
    await page.goto("/");
    const anatomy = page.locator("#anatomy");
    const height = await anatomy.evaluate((el) => el.getBoundingClientRect().height);
    // Pinned: half a chapter of scrolling later, the first chapter has not moved.
    const before = await anatomy.evaluate((el) => el.getBoundingClientRect().top);
    await page.evaluate((y) => window.scrollTo(0, y), Math.round(height / 2));
    await expect
      .poll(() => anatomy.evaluate((el) => Math.round(el.getBoundingClientRect().top)))
      .toBe(Math.round(before));
    // Chapter 3 pinned: its moment cards are showing.
    await page.evaluate((y) => window.scrollTo(0, y), Math.round(height * 4.5));
    await expect(page.locator("[data-moment]").first()).toHaveCSS("opacity", "1");
  });

  test("the button skips the story to the competitions", async ({ page }) => {
    await page.goto("/");
    // Clicked straight away, perhaps before the story's script has loaded and pinned the chapters.
    await page.getByRole("link", { name: "Choose a competition" }).first().click();
    await expect(page.getByRole("heading", { name: "Choose a competition" })).toBeInViewport();
    // And once it has.
    await page.goto("/");
    await page.locator("html.lenis").waitFor({ state: "attached" });
    await page.getByRole("link", { name: "Choose a competition" }).first().click();
    await expect(page.getByRole("heading", { name: "Choose a competition" })).toBeInViewport();
  });

  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("shows the same story still, without the canvas", async ({ page }) => {
      await page.goto("/");
      await expect(
        page.getByRole("heading", { level: 1, name: /Decode the game\./ }),
      ).toBeVisible();
      await expect(page.locator("canvas")).toHaveCount(0);
      await expect(
        page.getByRole("img", { name: /chance of winning through the IPL 2019 final/ }),
      ).toBeVisible();
      await expect(
        page.getByText("4,570,681", { exact: true }).filter({ visible: true }).first(),
      ).toBeVisible();
      await expect(page.getByRole("heading", { name: "Choose a competition" })).toBeVisible();
    });
  });
});
