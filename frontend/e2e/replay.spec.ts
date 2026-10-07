import { expect, test } from "@playwright/test";

test.describe("featured replay", () => {
  test("overview links to a featured replay", async ({ page }) => {
    await page.goto("/ipl");
    await expect(page.getByRole("heading", { name: /Decode the game/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Featured replays" })).toBeVisible();
    await page.getByRole("link", { name: /Replay the 2019 final/ }).click();
    await expect(page).toHaveURL(/\/matches\/1181768$/);
    await expect(
      page.getByRole("heading", { name: /Mumbai Indians\s+vs\s+Chennai Super Kings/ }),
    ).toBeVisible();
  });

  test("plays, steps and finishes the 2019 final", async ({ page }) => {
    await page.goto("/ipl/matches/1181768");
    const scoreboard = page.getByRole("region", { name: "Scoreboard" });
    await expect(scoreboard).toContainText("Before the first ball");

    await page.getByRole("button", { name: "Next ball" }).click();
    await expect(scoreboard).toContainText("1st innings");
    await expect(
      page.getByRole("region", { name: "Ball by ball" }).getByRole("listitem"),
    ).toHaveCount(1);

    await page.getByRole("button", { name: "Play" }).click();
    await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
    await expect
      .poll(async () =>
        page.getByRole("region", { name: "Ball by ball" }).getByRole("listitem").count(),
      )
      .toBeGreaterThan(1);
    await page.getByRole("button", { name: "Pause" }).click();

    await page.getByRole("button", { name: "Jump to end" }).click();
    await expect(scoreboard).toContainText("148/7");
    await expect(scoreboard).toContainText("Mumbai Indians won by 1 run");

    await page.getByRole("tab", { name: "Scorecard" }).click();
    const firstInnings = page.getByRole("region", { name: /Mumbai Indians, 1st innings/ });
    await expect(firstInnings).toContainText("149/8");
    await expect(firstInnings).toContainText("KA Pollard");
  });

  test("keyboard shortcuts drive the replay", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard shortcuts are a desktop feature");
    await page.goto("/ipl/matches/335982");
    await page.locator("[data-replay-ready]").waitFor();
    const scoreboard = page.getByRole("region", { name: "Scoreboard" });
    await page.keyboard.press("End");
    await expect(scoreboard).toContainText("Kolkata Knight Riders won by 140 runs");
    await page.keyboard.press("Home");
    await expect(scoreboard).toContainText("Before the first ball");
    await page.keyboard.press("ArrowRight");
    await expect(scoreboard).toContainText("1st innings");
  });
});
