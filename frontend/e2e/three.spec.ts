import { expect, test, type Page } from "@playwright/test";

// 3D scenes start as their poster and take over once loaded, after the visitor's first move; a
// reduced-motion visitor keeps the poster. The stadium and the ball come to life from laptop
// width up.

/** The visitor's first move, which lets the 3D start. */
async function move(page: Page) {
  await page.mouse.move(40, 40);
  await page.mouse.move(60, 80);
}

test.describe("3D scenes", () => {
  test("the home page stadium replaces its poster, loading nothing from other sites", async ({
    page,
    isMobile,
  }) => {
    test.skip(isMobile, "the stadium is a poster on phones");
    const site = new URL(test.info().project.use.baseURL!).hostname;
    const external: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (url.protocol.startsWith("http") && url.hostname !== site) external.push(url.href);
    });
    await page.goto("/");
    const scene = page.getByRole("img", { name: /A cricket stadium under floodlights/ });
    await expect(scene).toBeVisible();
    await page.waitForTimeout(1500);
    // Nothing 3D loads until the visitor moves.
    await expect(scene).toHaveAttribute("data-scene-state", "poster");
    await expect(scene.locator("canvas")).toHaveCount(0);
    await move(page);
    await expect(scene).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
    await expect(scene.locator("canvas")).toBeVisible();
    expect(external).toEqual([]);
  });

  test("the stadium's poster follows the theme", async ({ page }) => {
    await page.goto("/");
    const scene = page.getByRole("img", { name: /A cricket stadium under floodlights/ });
    await page.getByRole("radio", { name: "Dark theme" }).click();
    await expect(scene.locator('img[src*="stadium-night"]')).toBeVisible();
    await expect(scene.locator('img[src*="stadium-day"]')).toBeHidden();
    await page.getByRole("radio", { name: "Light theme" }).click();
    await expect(scene.locator('img[src*="stadium-day"]')).toBeVisible();
    await expect(scene.locator('img[src*="stadium-night"]')).toBeHidden();
  });

  test("a competition's home page has the ball", async ({ page, isMobile }) => {
    test.skip(isMobile, "the ball shows from laptop width up");
    await page.goto("/ipl");
    const scene = page.getByRole("img", { name: "A cricket ball, turning slowly" });
    await move(page);
    await expect(scene).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
  });

  test("the 404 page shows the stumps broken", async ({ page }) => {
    await page.goto("/no-such-page");
    const scene = page.getByRole("img", { name: /Stumps broken/ });
    await expect(scene).toBeVisible();
    await move(page);
    await expect(scene).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
  });

  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("the poster stays and no 3D loads", async ({ page }) => {
      await page.goto("/no-such-page");
      const scene = page.getByRole("img", { name: /Stumps broken/ });
      await expect(scene.locator("img")).toBeVisible();
      await move(page);
      await page.waitForTimeout(3000);
      await expect(scene).toHaveAttribute("data-scene-state", "poster");
      await expect(scene.locator("canvas")).toHaveCount(0);
    });
  });
});
