import { expect, test } from "@playwright/test";

// Lab notes are bundled with the web app; the 2019 final is a bundled featured replay.
test.describe("analytics lab", () => {
  test("opens a note from the index", async ({ page }) => {
    await page.goto("/ipl/lab");
    await expect(page.getByRole("heading", { level: 1, name: "Analytics Lab" })).toBeVisible();
    await page.getByRole("link", { name: /Is momentum real\?/ }).click();
    await expect(page).toHaveURL(/\/lab\/momentum$/);
    await expect(page.getByRole("heading", { level: 1, name: "Is momentum real?" })).toBeVisible();
    await expect(page.getByRole("region", { name: "The next two overs" })).toContainText(
      "Gained 15+",
    );
    await expect(page.getByRole("img", { name: /^Gained 15\+: [+−]\d/ }).first()).toBeVisible();
  });

  test("the pressure note checks leverage against what happened", async ({ page }) => {
    await page.goto("/ipl/lab/pressure");
    const check = page.getByRole("region", { name: "Does leverage work?" });
    await expect(check.getByRole("row")).toHaveCount(11);
    await expect(check).toContainText("Tensest");
    await expect(
      page.getByRole("region", { name: "The highest-pressure balls in IPL history" }),
    ).toContainText("needed from 1 ball");
  });

  test("the clutch note switches between batters and bowlers", async ({ page }) => {
    await page.goto("/ipl/lab/clutch");
    const halves = page.getByRole("region", { name: "Under pressure, season to season" });
    await expect(halves.getByRole("img", { name: /batters in odd seasons/ })).toBeVisible();
    await halves.getByRole("button", { name: "Bowlers" }).click();
    await expect(halves.getByRole("img", { name: /bowlers in odd seasons/ })).toBeVisible();
  });

  test("the replay shows pressure and momentum", async ({ page }) => {
    await page.goto("/ipl/matches/1181768");
    const panel = page.getByRole("region", { name: "Pressure and momentum" });
    await expect(panel).toContainText("Pressure on the next ball");
    await expect(panel).toContainText(/Low|Medium|High|Very high/);
    await page.locator("[data-replay-ready]").waitFor();
    await page.getByRole("button", { name: "Jump to end" }).click();
    await expect(panel).toContainText("The innings is over.");
    await expect(panel).toContainText("CSK");

    await page.getByRole("tab", { name: "Pressure" }).click();
    const peaks = page.getByRole("heading", { name: "Highest pressure so far" });
    await expect(peaks).toBeVisible();
    await page
      .getByRole("button", { name: /needed from 1/ })
      .first()
      .click();
    await expect(panel).toContainText("Very high");
  });
});
