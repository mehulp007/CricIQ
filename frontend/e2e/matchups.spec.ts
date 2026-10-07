import { expect, test } from "@playwright/test";

// Matchup Lab pages are served from the API.
test.describe("matchup lab", () => {
  test("opens a rivalry from the landing list", async ({ page }) => {
    await page.goto("/ipl/matchups");
    await expect(page.getByRole("heading", { name: "Matchup Lab" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "The most-played rivalries" })).toBeVisible();
    await page.getByRole("table").getByRole("link").first().click();

    await expect(page).toHaveURL(/batter=[\w-]+&bowler=[\w-]+/);
    await expect(
      page.getByRole("heading", { name: "Three ways to read the record" }),
    ).toBeVisible();
    await expect(page.getByRole("img", { name: /CricIQ estimate: \d/ }).first()).toBeVisible();
    const nextBall = page.getByRole("region", { name: "Next ball" });
    await nextBall.getByRole("button", { name: "Death overs" }).click();
    await expect(nextBall.getByRole("list", { name: "Next ball, death overs" })).toContainText(
      "Six",
    );
  });

  test("picks a batter and a bowler by search", async ({ page }) => {
    await page.goto("/ipl/matchups");
    await page.getByRole("combobox", { name: "Batter" }).fill("kohli");
    await page.getByRole("option", { name: /Virat Kohli/ }).click();
    await expect(page).toHaveURL(/batter=ba607b88/);
    await expect(
      page.getByRole("heading", { name: /Bowlers Virat Kohli has faced/ }),
    ).toBeVisible();

    await page.getByRole("combobox", { name: "Bowler" }).fill("bumrah");
    await page.getByRole("option", { name: /Jasprit Bumrah/ }).click();
    await expect(page).toHaveURL(
      /batter=ba607b88.*bowler=462411b3|bowler=462411b3.*batter=ba607b88/,
    );
    await expect(
      page.getByRole("heading", { level: 2, name: /Virat Kohli\s*vs\s*Jasprit Bumrah/ }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Death overs" }).click();
    await expect(page).toHaveURL(/phase=death/);
    await expect(page.getByText(/death overs/).first()).toBeVisible();
  });

  test("profiles link to head-to-head records", async ({ page }) => {
    await page.goto("/ipl/players/ba607b88");
    const panel = page.getByRole("region", { name: "Most-faced bowlers" });
    await expect(panel).toBeVisible();
    await panel.getByRole("table").getByRole("link").first().click();
    await expect(page).toHaveURL(/\/matchups\?batter=ba607b88&bowler=/);
  });

  test("model insights explain the ball-outcome model", async ({ page }) => {
    await page.goto("/ipl/models");
    await page.getByRole("tab", { name: "Ball outcome" }).click();
    await expect(
      page.getByRole("heading", { name: "Do head-to-head records predict the future?" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Wicket" }).click();
    await expect(page.getByText(/calibration error/)).toBeVisible();
  });
});
