import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Every key page must pass axe's WCAG 2.1 A and AA rules. API-backed pages
// need the API; the 2019 final is a bundled featured replay.
const PAGES = [
  "/",
  "/ipl",
  "/ipl/matches",
  "/ipl/matches/1181768",
  "/ipl/players",
  "/ipl/players/ba607b88",
  "/ipl/matchups",
  "/ipl/matchups?batter=ba607b88&bowler=462411b3",
  "/ipl/compare",
  "/ipl/compare?a=ba607b88&b=b8a55852",
  "/ipl/lab",
  "/ipl/lab/pressure",
  "/ipl/lab/clutch",
  "/ipl/lab/rivalries",
  "/ipl/teams",
  "/ipl/teams?season=2019",
  "/ipl/teams/MI",
  "/ipl/teams/h2h",
  "/ipl/teams/h2h?a=MI&b=CSK",
  "/ipl/simulator",
  "/ipl/models?tab=simulator",
  "/ipl/models",
  "/ipl/models?tab=win-probability",
  "/t20i",
  "/t20i/matches",
  "/t20i/matches/951373",
  "/t20i/players/4a8a2e3b",
  "/t20i/teams",
  "/t20i/teams/ENG",
  "/t20i/simulator",
  "/t20i/models",
  "/odi",
  "/odi/matches/1144530",
  "/odi/teams",
  "/odi/models",
  "/test",
  "/test/matches/1152848",
  "/test/teams/IND",
  "/test/chase",
  "/test/series",
  "/test/series/2020-21-india-tour-of-australia",
  "/test/teams/h2h?a=IND&b=AUS",
  "/test/compare?a=ba607b88&b=ba607b88&bf=ipl",
  "/test/lab/toss",
  "/odi/series/2019-mens-cricket-world-cup",
  "/odi/lab",
  "/t20i/lab/home",
  "/test/models",
  "/test/models?tab=win-probability",
  "/bbl",
  "/bbl/teams",
  "/bbl/simulator",
  "/bbl/models?tab=simulator",
  "/writeup",
  "/about",
];

// In both themes: with no stored preference the site follows the system colour scheme.
for (const colorScheme of ["dark", "light"] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    for (const path of PAGES) {
      test(`no accessibility violations on ${path}`, async ({ page }) => {
        await page.goto(path);
        await page.getByRole("main").waitFor();
        await expect(page.locator("html")).toHaveClass(
          colorScheme === "dark" ? /\bdark\b/ : /^(?!.*\bdark\b)/,
        );
        // Scan the page as it settles: let entrance animations (fades that start transparent)
        // finish first. Only those that run for a set time: endless ones (a breathing glow, a
        // loading shimmer) keep going, and ones tied to scrolling (the top bar's) have no end in
        // time (awaiting those crashes headless Chromium).
        await page.evaluate(() =>
          Promise.all(
            document
              .getAnimations()
              .filter((a) => {
                const end = a.effect?.getComputedTiming().endTime;
                return typeof end === "number" && Number.isFinite(end);
              })
              .map((a) => a.finished.catch(() => undefined)),
          ),
        );
        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();
        const summary = results.violations.map(
          (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
        );
        expect(summary).toEqual([]);
      });
    }
  });
}
