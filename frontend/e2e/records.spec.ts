import { expect, test } from "@playwright/test";

// The Records hub is served from the API, so it works on the fixture data too: the
// 2019 IPL final and a handful of other matches.
test.describe("records", () => {
  test("the hub groups every record and names its holder", async ({ page }) => {
    await page.goto("/ipl/records");
    await expect(page.getByRole("heading", { level: 1, name: "Records" })).toBeVisible();
    await expect(page.getByText(/In CricIQ's ball-by-ball data: IPL/)).toBeVisible();
    for (const group of ["Batting", "Bowling", "Partnerships", "Teams", "Ball by ball"]) {
      await expect(page.getByRole("heading", { level: 2, name: group })).toBeVisible();
    }
    await expect(page.getByRole("link", { name: /^Most runs: / })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Biggest swings from one ball: / })).toContainText(
      "Model estimate",
    );
  });

  test("a record opens its ranked list, and filters narrow it", async ({ page }) => {
    await page.goto("/ipl/records");
    await page.getByRole("link", { name: /^Highest scores: / }).click();
    await expect(page).toHaveURL(/\/ipl\/records\/highest-scores$/);
    await expect(page.getByRole("heading", { level: 1, name: "Highest scores" })).toBeVisible();
    const table = page.getByRole("table", { name: "Highest scores" });
    await expect(table.getByRole("row").nth(1)).toContainText("1");

    await page.getByRole("combobox", { name: "Team" }).click();
    await page.getByRole("option", { name: "Mumbai Indians" }).click();
    await expect(page).toHaveURL(/team=MI/);
    // Every innings is now Mumbai's, so none was against Mumbai.
    await expect(table.getByRole("row").nth(1)).toBeVisible();
    await expect(table.getByRole("cell", { name: "Mumbai Indians", exact: true })).toHaveCount(0);
  });

  test("a stand links to its batters and opens the replay at its first ball", async ({ page }) => {
    await page.goto("/ipl/records/highest-partnerships");
    const first = page.getByRole("table", { name: "Highest partnerships" }).getByRole("row").nth(1);
    await expect(first.getByRole("link")).toHaveCount(3);
    await first.getByRole("link", { name: /open the match at the ball/ }).click();
    await expect(page).toHaveURL(/\/ipl\/matches\/\d+\?ball=\d+\.\d+/);
  });

  test("partnerships filter by wicket", async ({ page }) => {
    await page.goto("/ipl/records/highest-partnerships");
    await page.getByRole("combobox", { name: "Wicket" }).click();
    await page.getByRole("option", { name: "1st wicket" }).click();
    await expect(page).toHaveURL(/wicket=1/);
  });

  test("a filter nothing matches says so, and an unknown record is not found", async ({ page }) => {
    await page.goto("/ipl/records/most-runs?venue=nowhere");
    await expect(page.getByText("Nothing matches these filters")).toBeVisible();
    await page.goto("/ipl/records/no-such-record");
    await expect(page.getByText(/Out of the ground/)).toBeVisible();
  });

  test("Tests have innings wins and no four-wicket list", async ({ page }) => {
    await page.goto("/test/records");
    await expect(page.getByRole("heading", { level: 1, name: "Records" })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Most four-wicket innings/ })).toHaveCount(0);
    await page.goto("/test/records/highest-scores");
    await expect(page.getByRole("table", { name: "Highest scores" })).toBeVisible();
  });

  test("the competition home shows headline records", async ({ page }) => {
    await page.goto("/ipl");
    const strip = page.getByRole("region", { name: "Headline records" });
    await expect(strip.getByRole("link", { name: /^Highest scores: / })).toBeVisible();
    await strip.getByRole("link", { name: "All records" }).click();
    await expect(page).toHaveURL(/\/ipl\/records$/);
  });
});
