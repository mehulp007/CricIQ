import { expect, test } from "@playwright/test";

// The tools tied together: records held on player pages, a match's note on its replay, a
// side's phases on its team page, and search for record lists and dates. The 2025 IPL final
// (1473511, 3 June 2025) is in every build of the data, including the test fixtures.

test.describe("connections between the tools", () => {
  test("a player page lists the records the player holds", async ({ page }) => {
    await page.goto("/ipl/records/most-runs");
    const leader = page.getByRole("table", { name: "Most runs" }).getByRole("link").first();
    const name = (await leader.textContent())?.trim() ?? "";
    await leader.click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(name);
    const held = page.getByRole("region", { name: "Records held" });
    await expect(held.getByRole("link", { name: "Most runs", exact: true })).toBeVisible();
    await expect(held).toContainText("The record");
    await held.getByRole("link", { name: "Most runs", exact: true }).click();
    await expect(page).toHaveURL(/\/ipl\/records\/most-runs$/);
  });

  test("a replay shows its match as the daily notes told it", async ({ page }) => {
    await page.goto("/ipl/matches/1473511");
    const note = page.getByRole("region", { name: "This match in the daily notes" });
    await expect(note).toContainText("Turning point");
    await note.getByRole("link", { name: /3 June 2025/ }).click();
    await expect(page).toHaveURL(/\/notes\/2025-06-03$/);
  });

  test("a team page links to its innings phase by phase", async ({ page }) => {
    await page.goto("/ipl/teams/MI");
    const phases = page.getByRole("region", { name: "How they bat and bowl" });
    await phases.getByRole("link", { name: "Phases for Mumbai Indians" }).click();
    await expect(page).toHaveURL(/\/ipl\/phases\?team=MI$/);
    await expect(
      page.getByRole("heading", { name: "Mumbai Indians: batting phase by phase" }),
    ).toBeVisible();
  });

  test("search finds record lists and days", async ({ page }) => {
    await page.goto("/ipl");
    await page.getByRole("button", { name: "Search" }).click();
    const search = page.getByRole("combobox", { name: /Search pages, players/ });
    await search.fill("highest partner");
    await page.getByRole("option", { name: /Highest partnerships/ }).click();
    await expect(page).toHaveURL(/\/ipl\/records\/highest-partnerships$/);

    await page.getByRole("button", { name: "Search" }).click();
    await page.getByRole("combobox", { name: /Search pages, players/ }).fill("3 June 2025");
    await page.getByRole("option", { name: /Daily note: Tuesday 3 June 2025/ }).click();
    await expect(page).toHaveURL(/\/notes\/2025-06-03$/);
  });

  test("About explains the new tools", async ({ page }) => {
    await page.goto("/about");
    for (const name of [
      "Phases: how innings are built",
      "Records: the ball-by-ball era",
      "Chart Studio",
      "On this day",
      "Daily notes: how they are written",
    ]) {
      await expect(page.getByRole("heading", { level: 2, name, exact: true })).toBeVisible();
    }
  });
});
