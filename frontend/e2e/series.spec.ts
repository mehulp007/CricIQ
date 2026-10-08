import { expect, test } from "@playwright/test";

// International depth (V2-7): series and tournaments, careers and comparisons across
// formats, and the Analytics Lab notes comparing formats. These pages read the API.
test.describe("series and tournaments", () => {
  test("a Test series opens from the list with its score and matches", async ({ page }) => {
    await page.goto("/test/series?team=IND&year=2021");
    await expect(
      page.getByRole("heading", { level: 1, name: "Series and tournaments" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: /India tour of Australia 2020\/21/ })
      .first()
      .click();
    await expect(page).toHaveURL(/\/test\/series\/2020-21-india-tour-of-australia$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "India tour of Australia 2020/21" }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Result", exact: true })).toContainText(/wins?/);
    await expect(page.getByRole("heading", { name: "The matches" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Most runs" })).toBeVisible();
    // A match of the series links back to it.
    await page.getByRole("link", { name: /Adelaide Oval/ }).click();
    await expect(page).toHaveURL(/\/test\/matches\/1223869$/);
    await expect(
      page
        .getByRole("navigation", { name: "Breadcrumb" })
        .getByRole("link", { name: "India tour of Australia 2020/21" }),
    ).toBeVisible();
  });

  test("a World Cup names its champions", async ({ page }) => {
    await page.goto("/odi/series/2019-mens-cricket-world-cup");
    await expect(
      page.getByRole("heading", { level: 1, name: "Men's Cricket World Cup 2019" }),
    ).toBeVisible();
    const result = page.getByRole("region", { name: "Result", exact: true });
    await expect(result).toContainText("Champions");
    await expect(result).toContainText("England");
    await expect(page.getByText("England beat New Zealand in the final")).toBeVisible();
  });

  test("the series list is international only", async ({ page }) => {
    expect((await page.goto("/ipl/series"))?.status()).toBe(404);
    expect((await page.goto("/t20i/series"))?.status()).toBe(200);
  });

  test("two national sides compare in every format", async ({ page }) => {
    await page.goto("/test/teams/h2h?a=IND&b=AUS");
    const table = page.getByRole("region", { name: "Record in every format" });
    await expect(table).toBeVisible();
    await expect(table.getByRole("row", { name: /^Test/ })).toBeVisible();
  });
});

test.describe("careers across formats", () => {
  test("a player's page has every competition's numbers and ratings", async ({ page }) => {
    await page.goto("/test/players/ba607b88");
    const careers = page.getByRole("region", { name: "Career in every competition" });
    await expect(careers).toContainText("100s/50s");
    await expect(careers).toContainText("Test");
    await expect(careers).toContainText("IPL");
  });

  test("compare sets a player's Tests beside another competition", async ({ page }) => {
    await page.goto("/test/compare?a=ba607b88&b=ba607b88&bf=ipl");
    await expect(
      page.getByText(/Virat Kohli in Tests against Virat Kohli in the IPL/),
    ).toBeVisible();
    await expect(
      page.getByRole("combobox", { name: "Competition of the second player" }),
    ).toContainText("IPL");
    await expect(page.getByText(/phases only compare within one format/)).toBeVisible();
  });
});

test.describe("analytics lab across formats", () => {
  test("every competition has the notes comparing formats", async ({ page }) => {
    await page.goto("/odi/lab");
    await expect(
      page.getByRole("link", { name: /Does the toss matter more in Tests\?/ }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: /Home advantage by format/ })).toBeVisible();
    // The IPL's own notes stay with the IPL.
    await expect(page.getByRole("link", { name: /Is momentum real\?/ })).toHaveCount(0);
    expect((await page.goto("/odi/lab/momentum"))?.status()).toBe(404);
  });

  test("the toss note answers with intervals", async ({ page }) => {
    await page.goto("/test/lab/toss");
    await expect(
      page.getByRole("heading", { level: 1, name: "Does the toss matter more in Tests?" }),
    ).toBeVisible();
    await expect(page.getByRole("img", { name: /^Tests: [+−]\d/ }).first()).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Toss winners' results by format" }),
    ).toContainText("ODIs");
  });

  test("the home note balances strength", async ({ page }) => {
    await page.goto("/t20i/lab/home");
    await expect(
      page.getByRole("heading", { name: "Home advantage between the same pairs of sides" }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Home sides' results by format" })).toContainText(
      "Tests",
    );
  });
});
