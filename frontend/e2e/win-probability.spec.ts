import { expect, test } from "@playwright/test";

test.describe("win probability", () => {
  test("follows the 2019 final to its last ball", async ({ page }) => {
    await page.goto("/matches/1181768");
    const scoreboard = page.getByRole("region", { name: "Scoreboard" });
    const wp = scoreboard.getByTestId("win-probability");
    await expect(wp).toBeVisible();
    await expect(wp.getByRole("img")).toHaveAttribute("aria-label", /Mumbai Indians \d+%/);
    await expect(page.getByRole("region", { name: "Why this estimate" })).toContainText(
      "Before a ball is bowled",
    );

    await page.getByRole("button", { name: "Next ball" }).click();
    const why = page.getByRole("region", { name: "Why this estimate" });
    await expect(why).toContainText("Wickets in hand");
    await expect(why).toContainText("Score for the stage");

    await page.getByRole("button", { name: "Jump to end" }).click();
    await expect(wp).toContainText("100%");
    await expect(why).toContainText("The result is settled");
    await expect(page.getByRole("tab", { name: "Win probability" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByRole("heading", { name: "Turning points so far" })).toBeVisible();
  });

  test("model insights link straight to the biggest swings", async ({ page }) => {
    await page.goto("/models");
    await expect(page.getByRole("heading", { name: "Model Insights", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Does 70% mean 70%?" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "What didn't make the cut" })).toBeVisible();

    const swings = page.getByRole("region", { name: "The biggest swings in IPL history" });
    await expect(swings.getByRole("link")).toHaveCount(10);
    await expect(swings.getByRole("link").first()).toHaveAttribute(
      "href",
      /^\/matches\/\d+\?ball=\d+\.\d+$/,
    );
  });

  test("a ball link opens the replay at that moment", async ({ page }) => {
    await page.goto("/matches/1181768?ball=2.118");
    const scoreboard = page.getByRole("region", { name: "Scoreboard" });
    await expect(scoreboard).toContainText("141/5");
    await expect(page.getByRole("region", { name: "Why this estimate" })).toContainText(
      "Need 9 from 6 balls",
    );
  });
});
