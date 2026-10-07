import { expect, test } from "@playwright/test";

// The Compare page is served from the API.
test.describe("compare", () => {
  test("picks two players by search and compares them", async ({ page }) => {
    await page.goto("/ipl/compare");
    await expect(page.getByRole("heading", { level: 1, name: "Compare players" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Try a classic" })).toBeVisible();

    await page.getByRole("combobox", { name: "Player A" }).fill("kohli");
    await page.getByRole("option", { name: /Virat Kohli/ }).click();
    await expect(page).toHaveURL(/a=ba607b88/);
    await page.getByRole("combobox", { name: "Player B" }).fill("mccullum");
    await page.getByRole("option", { name: /Brendon McCullum/ }).click();
    await expect(page).toHaveURL(/a=ba607b88.*b=b8a55852|b=b8a55852.*a=ba607b88/);

    const numbers = page.getByRole("region", { name: "Batting side by side" });
    await expect(numbers).toContainText("Strike rate");
    await expect(numbers).toContainText("Runs above par");
    await expect(page.getByRole("region", { name: "CricIQ Ratings" })).toContainText("Run scoring");
    await expect(
      page.getByRole("img", { name: /^Runs above par per 100 balls by season/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: "By age" }).click();
    await expect(
      page.getByRole("img", { name: /^Runs above par per 100 balls by age/ }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Swap players" }).click();
    await expect(page).toHaveURL(/a=b8a55852/);
  });

  test("bowlers are compared as bowlers", async ({ page }) => {
    await page.goto("/ipl/compare?a=462411b3&b=a12e1d51");
    const numbers = page.getByRole("region", { name: "Bowling side by side" });
    await expect(numbers).toContainText("Economy");
    await expect(numbers).toContainText("Runs saved per over");
    await expect(page.getByRole("region", { name: "CricIQ Ratings" })).toContainText(
      "Wicket-taking",
    );
  });

  test("profiles link to a comparison", async ({ page }) => {
    await page.goto("/ipl/players/ba607b88");
    await page.getByRole("main").getByRole("link", { name: "Compare", exact: true }).click();
    await expect(page).toHaveURL(/\/compare\?a=ba607b88$/);
    await expect(page.getByRole("button", { name: "Clear player a" })).toBeVisible();
  });

  test("unknown players are reported", async ({ page }) => {
    await page.goto("/ipl/compare?a=ba607b88&b=nobody");
    await expect(page.getByText("One of these players could not be found.")).toBeVisible();
  });

  test("model insights explain the ratings", async ({ page }) => {
    await page.goto("/ipl/models");
    await page.getByRole("tab", { name: "Ratings" }).click();
    await expect(
      page.getByRole("heading", { name: "Bowling: runs conceded tell you more than wickets" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Do style profiles identify a player?" }),
    ).toContainText("Median rank");
  });
});
