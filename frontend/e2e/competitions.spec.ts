import { expect, test } from "@playwright/test";

// Every competition has its own pages under /[competition]/. These run on the
// fixture data in CI (a few matches per competition) and on the full data locally.

test.describe("competitions", () => {
  test("the home page leads with every competition", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Choose a competition" })).toBeVisible();
    for (const label of ["IPL", "BBL", "PSL", "CPL", "SA20", "T20I", "ODI"]) {
      await expect(page.getByRole("link", { name: new RegExp(`^${label}\\b`) })).toBeVisible();
    }
    // Test cricket is listed, never linked.
    await expect(page.getByText("Coming in V2-6")).toBeVisible();
    await expect(page.getByRole("link", { name: /^Test/ })).toHaveCount(0);
    await page.getByRole("link", { name: /^T20I\b/ }).click();
    await expect(page).toHaveURL(/\/t20i$/);
    await expect(page.getByText("T20I · 2005 onward")).toBeVisible();
  });

  test("the switcher keeps the same kind of page", async ({ page }) => {
    await page.goto("/ipl/matches");
    await page.getByTestId("competition-switcher").click();
    await page.getByRole("option", { name: /^T20I/ }).click();
    await expect(page).toHaveURL(/\/t20i\/matches$/);
    await expect(page.getByText(/^Every men's T20 international since 2005/)).toBeVisible();
    // A page about one match goes to the other competition's list.
    await page.goto("/ipl/matches/1181768");
    await page.getByTestId("competition-switcher").click();
    await page.getByRole("option", { name: /^BBL/ }).click();
    await expect(page).toHaveURL(/\/bbl\/matches$/);
  });

  test("old links land on the IPL's pages", async ({ page }) => {
    await page.goto("/matches/1181768?ball=1.60");
    await expect(page).toHaveURL(/\/ipl\/matches\/1181768\?ball=1\.60$/);
    await page.goto("/teams/MI");
    await expect(page).toHaveURL(/\/ipl\/teams\/MI$/);
  });

  test("a T20I replays ball by ball with its own model", async ({ page }) => {
    // The 2016 World T20 final is a bundled featured replay.
    await page.goto("/t20i/matches/951373");
    await expect(page.getByRole("heading", { name: /England\s+vs\s+West Indies/ })).toBeVisible();
    await expect(page.getByTestId("win-probability")).toBeVisible();
    await expect(page.getByText(/adjusted for the two squads' records/)).toBeVisible();
    // No simulator serves T20Is, so there is no what-if sandbox.
    await expect(page.getByRole("region", { name: "What if?" })).toHaveCount(0);
  });

  test("an ODI replays over fifty overs with its own model", async ({ page }) => {
    // The 2019 World Cup final is a bundled featured replay.
    await page.goto("/odi/matches/1144530");
    await expect(page.getByRole("heading", { name: /New Zealand\s+vs\s+England/ })).toBeVisible();
    await expect(page.getByTestId("win-probability")).toBeVisible();
    await page.locator("[data-replay-ready]").waitFor();
    await page.getByRole("button", { name: "Jump to end" }).click();
    // Tied at 241, then a tied super over (15 each), settled on boundaries.
    await expect(page.getByText("Super over 1").first()).toBeVisible();
    await expect(
      page.getByText("Match tied (England won on boundaries after a tied super over)").first(),
    ).toBeVisible();
  });

  test("ODI sides have records by year and by opponent", async ({ page }) => {
    await page.goto("/odi/teams");
    await expect(page.getByRole("heading", { name: "Teams", level: 1 })).toBeVisible();
    await expect(page.getByText(/Every side in men's ODIs since 2002/)).toBeVisible();
    await page.goto("/odi/teams/ENG");
    await expect(page.getByRole("heading", { name: "England", level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Year by year", exact: true })).toBeVisible();
  });

  test("a bowl-out tie says so", async ({ page }) => {
    await page.goto("/t20i/matches?season=2007");
    await expect(page.getByText("Match tied (India won the bowl-out)").first()).toBeVisible();
  });

  test("national sides have records by year and by opponent", async ({ page }) => {
    await page.goto("/t20i/teams");
    await expect(page.getByRole("heading", { name: "Teams", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: /league table/ })).toHaveCount(0);
    await page.goto("/t20i/teams/ENG");
    await expect(page.getByRole("heading", { name: "England", level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Year by year", exact: true })).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Against each opponent", exact: true }),
    ).toBeVisible();
  });

  test("player pages link the player's other competitions", async ({ page }) => {
    await page.goto("/t20i/players/4a8a2e3b");
    const tabs = page.getByRole("navigation", { name: "Competitions" });
    await expect(tabs.getByRole("link", { name: "T20I" })).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("region", { name: "Every competition", exact: true }),
    ).toBeVisible();
    await tabs.getByRole("link", { name: "IPL" }).click();
    await expect(page).toHaveURL(/\/ipl\/players\/4a8a2e3b$/);
  });

  test("competitions without a simulator say why", async ({ page }) => {
    await page.goto("/t20i/simulator");
    await expect(page.getByRole("heading", { name: "No T20I simulator yet" })).toBeVisible();
    await expect(page.getByText(/failed its gate/)).toBeVisible();
    await page.getByRole("link", { name: "IPL simulator" }).click();
    await expect(page).toHaveURL(/\/ipl\/simulator$/);
  });

  test("a league whose backtest passed has a simulator", async ({ page }) => {
    await page.goto("/bbl/simulator");
    await expect(page.getByRole("heading", { level: 1, name: "Match Simulator" })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Season" })).toContainText(/BBL \d{4}\/\d{2}/);
    const teamA = page.getByRole("region", { name: "Team A" });
    await expect(
      teamA.getByRole("list", { name: "Team A batting order" }).getByRole("listitem"),
    ).toHaveCount(11);
    await page.getByRole("button", { name: /Simulate 10,000 matches/ }).click();
    const result = page.getByRole("region", { name: "Who wins" });
    await expect(result).toContainText("simulated matches", { timeout: 60_000 });
    await expect(result).toContainText("Model simulation");
  });

  test("a league replay has the what-if sandbox", async ({ page }) => {
    // The BBL 2023/24 final is a bundled featured replay.
    await page.goto("/bbl/matches/1386137");
    await page.locator("[data-replay-ready]").waitFor();
    await page.getByRole("button", { name: "Jump to end" }).click();
    for (let i = 0; i < 9; i += 1)
      await page.getByRole("button", { name: "Previous ball" }).click();
    const panel = page.getByRole("region", { name: "What if?" });
    await panel.getByRole("button", { name: "Add 10 runs" }).click();
    await panel.getByRole("button", { name: "Simulate the what-if" }).click();
    await expect(panel).toContainText("win chance", { timeout: 60_000 });
  });

  test("model insights show the pooled models on the competition's own matches", async ({
    page,
  }) => {
    await page.goto("/t20i/models");
    await expect(
      page.getByRole("heading", { name: "T20I Model Insights", level: 1 }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "How the models did on T20Is" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Simulator" })).toHaveCount(0);
  });

  test("the Analytics Lab covers the IPL only", async ({ page }) => {
    const response = await page.goto("/t20i/lab");
    expect(response?.status()).toBe(404);
    expect((await page.goto("/t20i/lab/momentum"))?.status()).toBe(404);
    expect((await page.goto("/ipl/lab/momentum"))?.status()).toBe(200);
  });
});
