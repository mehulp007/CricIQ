import { expect, test } from "@playwright/test";

// No page may scroll sideways: wide tables scroll inside their own region, and long names
// (venues, players) truncate instead of widening the page.
const PAGES = [
  "/",
  "/ipl",
  "/ipl/matches",
  "/ipl/matches/1181768",
  "/ipl/players",
  "/ipl/players/ba607b88",
  "/ipl/teams",
  "/ipl/teams/MI",
  "/ipl/models",
  "/ipl/simulator",
  "/test/series",
  "/test/matches/1152848",
  "/writeup",
];

for (const path of PAGES) {
  test(`no sideways scrolling on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.getByRole("main").waitFor();
    // Measure the settled page, once lazy panels and fonts have loaded.
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
