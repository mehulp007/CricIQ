import { expect, test, type Page } from "@playwright/test";

// The replay's over-by-over view: the Manhattan chart first, the 3D view once the visitor moves
// on a laptop-sized screen, a switch between them that is remembered, and overs that seek.

const FINAL = "/ipl/matches/1181768";

async function openAtEnd(page: Page) {
  await page.goto(FINAL);
  await page.locator("[data-replay-ready]").waitFor();
  await page.mouse.move(40, 40);
  await page.mouse.move(80, 120);
  await page.getByRole("button", { name: "Jump to end" }).click();
}

test.describe("over by over", () => {
  test("phones get the chart, with no 3D to switch to", async ({ page, isMobile }) => {
    test.skip(!isMobile, "the phone layout");
    await openAtEnd(page);
    const panel = page.getByRole("region", { name: "Over by over" });
    await expect(panel.getByTestId("overs-chart")).toBeVisible();
    await expect(panel.getByRole("group", { name: "View" })).toHaveCount(0);
    await expect(panel.getByTestId("overs-3d")).toHaveCount(0);
  });

  test("the 3D view takes over, and an over clicked replays it", async ({ page, isMobile }) => {
    test.skip(isMobile, "the 3D view is for laptop-sized screens");
    await openAtEnd(page);
    const panel = page.getByRole("region", { name: "Over by over" });
    const view = panel.getByTestId("overs-3d");
    await expect(view).toHaveAttribute("data-scene-state", "3d", { timeout: 30_000 });
    await expect(panel.getByTestId("overs-chart")).toHaveCount(0);

    // Sweep the pointer across the bars until one is under it.
    await view.scrollIntoViewIfNeeded();
    const box = (await view.boundingBox())!;
    let found = false;
    for (let y = 0.35; y <= 0.75 && !found; y += 0.05) {
      for (let x = 0.15; x <= 0.85 && !found; x += 0.03) {
        await page.mouse.move(box.x + box.width * x, box.y + box.height * y);
        found = await panel
          .getByText(/Click to replay it\.$/)
          .isVisible()
          .catch(() => false);
      }
    }
    expect(found, "an over under the pointer").toBe(true);
    const caption = await panel.getByText(/Click to replay it\.$/).textContent();
    const over = Number(caption!.match(/over (\d+)/)![1]);
    await page.mouse.down();
    await page.mouse.up();
    // The replay moved to the over's first ball.
    const scoreboard = page.getByRole("region", { name: "Scoreboard" });
    await expect(scoreboard).toContainText(`Ball ${over - 1}.1`);
  });

  test("the chart view is remembered", async ({ page, isMobile }) => {
    test.skip(isMobile, "the switch shows on laptop-sized screens");
    await openAtEnd(page);
    const panel = page.getByRole("region", { name: "Over by over" });
    await panel.getByRole("button", { name: "Chart" }).click();
    await expect(panel.getByRole("button", { name: "Chart" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(panel.getByTestId("overs-chart")).toBeVisible();
    await expect(panel.getByTestId("overs-3d")).toHaveCount(0);
    await page.reload();
    await page.locator("[data-replay-ready]").waitFor();
    // The switch appears once 3D may start, after the visitor moves.
    await page.mouse.move(40, 40);
    await page.mouse.move(80, 120);
    await expect(
      page.getByRole("region", { name: "Over by over" }).getByRole("button", { name: "Chart" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("the timeline marks every wicket", async ({ page }) => {
    await page.goto(FINAL);
    await page.locator("[data-replay-ready]").waitFor();
    // 8 MI wickets and 7 CSK ones, plus the innings break.
    await expect(page.getByTestId("replay-marks").locator("span")).toHaveCount(16);
  });
});
