import { expect, test } from "@playwright/test";

// These flows need the API; the featured-replay specs do not.
test.describe("match explorer", () => {
  test("lists matches and filters to playoffs", async ({ page }) => {
    await page.goto("/ipl/matches");
    await expect(page.getByRole("heading", { name: "Match Explorer" })).toBeVisible();
    const cards = page.getByRole("main").getByRole("listitem");
    await expect(cards.first()).toBeVisible();

    await page.getByRole("button", { name: "Playoffs only" }).click();
    await expect(page).toHaveURL(/playoffs=true/);
    await expect(page.getByRole("button", { name: "Playoffs only" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    for (const text of await cards.allInnerTexts()) {
      expect(text).toMatch(/Final|Qualifier|Eliminator|Semi|Play-Off/);
    }
  });

  test("opens an API-backed match replay", async ({ page }) => {
    await page.goto("/ipl/matches");
    await page.getByRole("main").getByRole("link").first().click();
    await expect(page).toHaveURL(/\/matches\/\d+$/);
    await page.getByRole("button", { name: "Jump to end" }).click();
    await expect(page.getByRole("region", { name: "Scoreboard" })).toContainText(
      /won|tied|No result/,
    );
    // Win probability comes from the API for matches that are not bundled.
    await expect(page.getByTestId("win-probability")).toBeVisible();
  });
});

test.describe("data freshness", () => {
  test("the overview leads with the latest matches", async ({ page }) => {
    await page.goto("/ipl");
    const latest = page.getByRole("region", { name: "Latest matches" });
    await expect(latest.getByRole("listitem").first()).toBeVisible();
    await latest.getByRole("listitem").first().getByRole("link").click();
    await expect(page).toHaveURL(/\/matches\/\d+$/);
  });

  test("the top bar says how fresh the data is", async ({ page, isMobile }) => {
    test.skip(isMobile, "the freshness note is shown from tablet width up");
    await page.goto("/ipl/matches");
    await expect(page.getByTestId("data-freshness")).toHaveText(/^Data (updated|to) \d/);
  });
});
