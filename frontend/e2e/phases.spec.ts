import { expect, test } from "@playwright/test";

// Phase Analysis is served from the API. The 2019 IPL final (MI v CSK) and the
// Headingley 2019 Test are in every build of the data, including the test fixtures.
test.describe("phases", () => {
  test("shows each phase, the over-by-over chart, results and leaders", async ({ page }) => {
    await page.goto("/ipl/phases");
    await expect(page.getByRole("heading", { level: 1, name: "Phases" })).toBeVisible();
    const cards = page.getByRole("list", { name: "Phases" });
    for (const phase of ["Powerplay", "Middle overs", "Death overs"]) {
      await expect(cards.getByRole("heading", { name: phase, exact: true })).toBeVisible();
    }
    await expect(cards).toContainText("Overs 1–6");
    await expect(page.getByRole("img", { name: /Runs and wickets in each over/ })).toBeVisible();
    await expect(page.getByText(/In CricIQ's ball-by-ball data: IPL/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Batting first or chasing" })).toContainText(
      "Won batting first",
    );
    await expect(page.getByRole("tab", { name: "Death overs" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await page.getByRole("tab", { name: "Powerplay" }).click();
    await expect(page.getByRole("table", { name: "Powerplay: batters" })).toBeVisible();
  });

  test("a leader opens their player page", async ({ page }) => {
    await page.goto("/ipl/phases");
    const batters = page.getByRole("table", { name: "Death overs: batters" });
    const first = batters.getByRole("link").first();
    const name = (await first.textContent())?.trim() ?? "";
    await first.click();
    await expect(page).toHaveURL(/\/ipl\/players\/[0-9a-f]{8}$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(name);
  });

  test("filters live in the URL and narrow the figures to a team", async ({ page }) => {
    await page.goto("/ipl/phases");
    await page.getByRole("combobox", { name: "Team" }).click();
    await page.getByRole("option", { name: "Mumbai Indians" }).click();
    await expect(page).toHaveURL(/team=MI/);
    await expect(
      page.getByRole("heading", { name: "Mumbai Indians: batting phase by phase" }),
    ).toBeVisible();
    await expect(page.getByRole("region", { name: "Batting first or chasing" })).toContainText(
      "Mumbai Indians won batting first",
    );

    await page.getByRole("combobox", { name: "Innings" }).click();
    await page.getByRole("option", { name: "Chasing" }).click();
    await expect(page).toHaveURL(/innings=2/);

    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page).toHaveURL(/\/ipl\/phases$/);
  });

  test("a filter nothing matches says so", async ({ page }) => {
    await page.goto("/ipl/phases?venue=nowhere");
    await expect(page.getByText("No innings match these filters")).toBeVisible();
  });

  test("Tests have the new ball, the middle and the second new ball", async ({ page }) => {
    await page.goto("/test/phases");
    const cards = page.getByRole("list", { name: "Phases" });
    for (const phase of ["New ball", "Middle overs", "Second new ball"]) {
      await expect(cards.getByRole("heading", { name: phase, exact: true })).toBeVisible();
    }
    await expect(cards).toContainText("Overs 81 onwards");
    await expect(page.getByRole("img", { name: /Runs and wickets by ten overs/ })).toBeVisible();
    await expect(page.getByRole("region", { name: "Batting first or second" })).toBeVisible();
    await page.getByRole("combobox", { name: "Innings" }).click();
    await expect(page.getByRole("option", { name: "4th innings" })).toBeVisible();
  });

  test("the sidebar and the competition home link to it", async ({ page }) => {
    await page.goto("/odi");
    await page
      .getByRole("link", { name: /^Phases/ })
      .first()
      .click();
    await expect(page).toHaveURL(/\/odi\/phases$/);
    await expect(page.getByRole("heading", { level: 1, name: "Phases" })).toBeVisible();
  });
});
