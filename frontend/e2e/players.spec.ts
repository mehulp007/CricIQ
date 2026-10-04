import { expect, test } from "@playwright/test";

// Player Lab pages are served from the API.
test.describe("player lab", () => {
  test("searches the directory and opens a profile", async ({ page }) => {
    await page.goto("/players");
    await expect(page.getByRole("heading", { name: "Player Lab" })).toBeVisible();

    await page.getByRole("searchbox", { name: "Search players" }).fill("bumrah");
    await expect(page).toHaveURL(/q=bumrah/);
    const link = page.getByRole("link", { name: "Jasprit Bumrah" });
    await expect(link).toBeVisible();
    await link.click();

    await expect(page).toHaveURL(/\/players\/[\w-]+$/);
    await expect(page.getByRole("heading", { level: 1, name: "Jasprit Bumrah" })).toBeVisible();
    // A bowler's profile opens on bowling, measured against par.
    await expect(page.getByRole("tab", { name: "Bowling" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(page.getByRole("region", { name: "CricIQ Ratings" })).toContainText("Economy");
    await expect(page.getByRole("region", { name: "By phase", exact: true })).toContainText(
      "Death overs",
    );
  });

  test("narrows the season window and switches splits", async ({ page }) => {
    await page.goto("/players?q=kohli");
    await page.getByRole("link", { name: "Virat Kohli" }).click();
    await expect(page.getByRole("tab", { name: "Batting" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByRole("button", { name: "Last 3 seasons" }).click();
    await expect(page).toHaveURL(/from=\d{4}/);
    await expect(page.getByRole("button", { name: "Last 3 seasons" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const splits = page.getByRole("region", { name: "Splits", exact: true });
    await splits.getByRole("button", { name: "Opposition" }).click();
    await expect(splits.getByRole("table")).toContainText("vs ");
    await splits.getByRole("button", { name: "Bowler type" }).click();
    await expect(splits.getByRole("table")).toContainText("vs pace");
  });

  test("scorecard names link to player profiles", async ({ page }) => {
    await page.goto("/matches/1181768");
    await page.getByRole("button", { name: "Jump to end" }).click();
    await page.getByRole("tab", { name: "Scorecard" }).click();
    await page.getByRole("link", { name: "JJ Bumrah" }).first().click();
    await expect(page.getByRole("heading", { level: 1, name: "Jasprit Bumrah" })).toBeVisible();
  });
});
