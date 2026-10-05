import { expect, test } from "@playwright/test";

// The simulator runs in the API. MI and CSK appear in every build of the data,
// including the test fixtures; the 2019 final is a bundled featured replay.
test.describe("simulator", () => {
  test("simulates two XIs and shows the spread of results", async ({ page }) => {
    await page.goto("/simulator");
    await expect(page.getByRole("heading", { level: 1, name: "Match Simulator" })).toBeVisible();
    const teamA = page.getByRole("region", { name: "Team A" });
    await expect(
      teamA.getByRole("list", { name: "Team A batting order" }).getByRole("listitem"),
    ).toHaveCount(11);

    await page
      .getByRole("button", { name: /bat first/ })
      .first()
      .click();
    await page.getByRole("button", { name: /Simulate 10,000 matches/ }).click();
    const result = page.getByRole("region", { name: "Who wins" });
    await expect(result).toContainText("simulated matches", { timeout: 60_000 });
    await expect(result).toContainText("Model simulation");
    await expect(page.getByRole("region", { name: "First-innings totals" })).toContainText(
      "batting first: median",
    );
    await expect(
      page.getByRole("region", { name: "The typical simulated scorecard" }).getByRole("table"),
    ).toHaveCount(4);
  });

  test("edits the XI and refuses too few bowlers", async ({ page }) => {
    await page.goto("/simulator");
    const teamA = page.getByRole("region", { name: "Team A" });
    const boxes = teamA.getByRole("checkbox", { checked: true });
    await expect(boxes.first()).toBeVisible();
    while ((await boxes.count()) > 4) await boxes.first().uncheck();
    await expect(teamA).toContainText("at least 5 bowling options");
    await expect(page.getByRole("button", { name: /Simulate 10,000 matches/ })).toBeDisabled();

    const first = teamA.getByRole("listitem").first();
    const name = (await first.locator("span.truncate").first().textContent()) ?? "";
    await teamA.getByRole("button", { name: `Move ${name} down` }).click();
    await expect(teamA.getByRole("listitem").nth(1)).toContainText(name);
  });

  test("picks the XI from the season's squad", async ({ page }) => {
    await page.goto("/simulator");
    await expect(page.getByRole("combobox", { name: "Season" })).toContainText("IPL");
    const teamA = page.getByRole("region", { name: "Team A" });
    const xi = teamA.getByRole("list", { name: "Team A batting order" }).getByRole("listitem");
    await expect(xi).toHaveCount(11);
    const last = xi.last();
    const name = (await last.locator("span.truncate").first().textContent()) ?? "";
    await teamA.getByRole("button", { name: `Leave ${name} out` }).click();
    await expect(xi).toHaveCount(10);
    await expect(teamA).toContainText("Pick 11 players");
    await expect(page.getByRole("button", { name: /Simulate 10,000 matches/ })).toBeDisabled();

    await teamA.getByRole("button", { name: `Add ${name} to the XI` }).click();
    await expect(xi).toHaveCount(11);
    await expect(xi.last()).toContainText(name);
  });

  test("the replay's what-if moves the win probability", async ({ page }) => {
    await page.goto("/matches/1181768");
    await page.locator("[data-replay-ready]").waitFor();
    await page.getByRole("button", { name: "Jump to end" }).click();
    for (let i = 0; i < 9; i += 1)
      await page.getByRole("button", { name: "Previous ball" }).click();
    const panel = page.getByRole("region", { name: "What if?" });
    await expect(panel).toContainText("Change the score");
    await panel.getByRole("button", { name: "Add 10 runs" }).click();
    await panel.getByRole("button", { name: "Simulate the what-if" }).click();
    await expect(panel).toContainText("win chance", { timeout: 60_000 });
    await expect(panel).toContainText("pts");
  });
});
