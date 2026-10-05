import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Every key page must pass axe's WCAG 2.1 A and AA rules. API-backed pages
// need the API; the 2019 final is a bundled featured replay.
const PAGES = [
  "/",
  "/matches",
  "/matches/1181768",
  "/players",
  "/players/ba607b88",
  "/matchups",
  "/matchups?batter=ba607b88&bowler=462411b3",
  "/compare",
  "/compare?a=ba607b88&b=b8a55852",
  "/lab",
  "/lab/pressure",
  "/lab/clutch",
  "/lab/rivalries",
  "/teams",
  "/teams?season=2019",
  "/teams/MI",
  "/teams/h2h",
  "/teams/h2h?a=MI&b=CSK",
  "/simulator",
  "/models?tab=simulator",
  "/models",
  "/about",
];

for (const path of PAGES) {
  test(`no accessibility violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.getByRole("main").waitFor();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const summary = results.violations.map(
      (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
    );
    expect(summary).toEqual([]);
  });
}
