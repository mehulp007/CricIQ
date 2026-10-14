import { expect, test } from "@playwright/test";

// 3D scenes start as their poster and take over once loaded; a reduced-motion visitor keeps the
// poster. The home page's ball shows from tablet width up.
test.describe("3D scenes", () => {
  test("the home page ball replaces its poster, loading nothing from other sites", async ({
    page,
    isMobile,
  }) => {
    test.skip(isMobile, "the home page ball shows from tablet width up");
    const site = new URL(test.info().project.use.baseURL!).hostname;
    const external: string[] = [];
    page.on("request", (r) => {
      const url = new URL(r.url());
      if (url.protocol.startsWith("http") && url.hostname !== site) external.push(url.href);
    });
    await page.goto("/");
    const scene = page.getByRole("img", { name: "A cricket ball, turning slowly" });
    await expect(scene).toBeVisible();
    await expect(scene).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
    await expect(scene.locator("canvas")).toBeVisible();
    expect(external).toEqual([]);
  });

  test("the 404 page shows the stumps broken", async ({ page }) => {
    await page.goto("/no-such-page");
    const scene = page.getByRole("img", { name: /Stumps broken/ });
    await expect(scene).toBeVisible();
    await expect(scene).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
  });

  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });

    test("the poster stays and no 3D loads", async ({ page }) => {
      await page.goto("/no-such-page");
      const scene = page.getByRole("img", { name: /Stumps broken/ });
      await expect(scene.locator("img")).toBeVisible();
      await page.waitForTimeout(3000);
      await expect(scene).toHaveAttribute("data-scene-state", "poster");
      await expect(scene.locator("canvas")).toHaveCount(0);
    });
  });
});
