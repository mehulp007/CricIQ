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
  "/ipl/phases",
  "/ipl/studio",
  "/ipl/studio?t=batting&size=portrait",
  "/ipl/records",
  "/ipl/records/highest-partnerships",
  "/ipl/teams/MI",
  "/ipl/models",
  "/ipl/simulator",
  "/test/series",
  "/test/phases",
  "/test/studio?t=match",
  "/test/records/highest-chases",
  "/test/matches/1152848",
  "/on-this-day/may-12",
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
