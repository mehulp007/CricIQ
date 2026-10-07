import { expect, test } from "@playwright/test";

// Team pages are served from the API. MI and CSK met in the 2019 final, which
// is in every build of the data, including the test fixtures.
test.describe("teams", () => {
  test("lists franchises and shows any season's league table", async ({ page }) => {
    await page.goto("/ipl/teams");
    await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Mumbai Indians/ }).first()).toBeVisible();

    await page.getByRole("combobox", { name: "League table season" }).click();
    await page.getByRole("option", { name: "2019", exact: true }).click();
    await expect(page).toHaveURL(/season=2019/);
    const table = page.getByRole("region", { name: "2019 league table" });
    await expect(table.getByRole("row", { name: /Mumbai Indians/ })).toContainText("Champions");
    await expect(table.getByRole("row", { name: /Chennai Super Kings/ })).toContainText(
      "Runners-up",
    );
  });

  test("a franchise page covers seasons, situations and rivals", async ({ page }) => {
    await page.goto("/ipl/teams");
    await page
      .getByRole("region", { name: "Franchises" })
      .getByRole("link", { name: /Mumbai Indians/ })
      .click();
    await expect(page).toHaveURL(/\/teams\/MI$/);
    await expect(page.getByRole("heading", { level: 1, name: "Mumbai Indians" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Season by season" })).toContainText("Champions");
    await expect(page.getByRole("region", { name: "Results by situation" })).toContainText(
      "Batting first",
    );
    await expect(page.getByRole("region", { name: "How they bat and bowl" })).toContainText(
      "Powerplay",
    );

    await page.getByRole("combobox", { name: "From season" }).click();
    await page.getByRole("option", { name: "2019", exact: true }).click();
    await expect(page).toHaveURL(/from=2019/);

    await page
      .getByRole("region", { name: "Against each opponent" })
      .getByRole("link", { name: "MI against CSK, head to head" })
      .click();
    await expect(page).toHaveURL(/\/teams\/h2h\?a=MI&b=CSK/);
  });

  test("head to head picks two teams and sets the record against form", async ({ page }) => {
    await page.goto("/ipl/teams/h2h");
    await expect(page.getByRole("heading", { name: "Pick two teams" })).toBeVisible();
    await page.getByRole("combobox", { name: "First team" }).click();
    await page.getByRole("option", { name: "Mumbai Indians" }).click();
    await expect(page).toHaveURL(/a=MI/);
    await page.getByRole("combobox", { name: "Second team" }).click();
    await page.getByRole("option", { name: "Chennai Super Kings" }).click();
    await expect(page).toHaveURL(/a=MI.*b=CSK/);

    await expect(page.getByRole("region", { name: "The record" })).toContainText("meeting");
    await expect(page.getByRole("region", { name: "More than form?" })).toContainText(
      "expected to win",
    );
    await expect(
      page.getByRole("region", { name: "Every meeting" }).locator('a[href="/ipl/matches/1181768"]'),
    ).toBeVisible();

    await page.getByRole("button", { name: "Swap teams" }).click();
    await expect(page).toHaveURL(/a=CSK.*b=MI/);
  });

  test("the rivalries note is in the Analytics Lab", async ({ page }) => {
    await page.goto("/ipl/lab");
    await page.getByRole("link", { name: /Do rivalries and close finishes repeat\?/ }).click();
    await expect(page).toHaveURL(/\/lab\/rivalries$/);
    await expect(
      page.getByRole("region", { name: "Do rivalry leaders keep winning?" }),
    ).toContainText("Won 60%+");
  });
});
