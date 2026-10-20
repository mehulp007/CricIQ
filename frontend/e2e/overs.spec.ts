import { expect, test } from "@playwright/test";

// The replay's over-by-over chart and its timeline marks.

const FINAL = "/ipl/matches/1181768";

test.describe("over by over", () => {
  test("the Manhattan chart shows the overs bowled", async ({ page }) => {
    await page.goto(FINAL);
    await page.locator("[data-replay-ready]").waitFor();
    await page.getByRole("button", { name: "Jump to end" }).click();
    const panel = page.getByRole("region", { name: "Over by over" });
    await expect(panel.getByTestId("overs-chart")).toBeVisible();
    await expect(panel.getByText("Mumbai Indians")).toBeVisible();
    await expect(panel.getByText("Chennai Super Kings")).toBeVisible();
  });

  test("the timeline marks every wicket", async ({ page }) => {
    await page.goto(FINAL);
    await page.locator("[data-replay-ready]").waitFor();
    // 8 MI wickets and 7 CSK ones, plus the innings break.
    await expect(page.getByTestId("replay-marks").locator(":scope > span")).toHaveCount(16);
  });
});
