import { test } from "@playwright/test";

// The key pages of the redesign, captured in both themes (see playwright.visual.config.ts).
const PAGES: [string, string][] = [
  ["home", "/"],
  ["ipl", "/ipl"],
  ["matches", "/ipl/matches"],
  ["replay", "/ipl/matches/1181768"],
  ["test-replay", "/test/matches/1152848"],
  ["players", "/ipl/players"],
  ["player", "/ipl/players/ba607b88"],
  ["teams", "/ipl/teams"],
  ["models", "/ipl/models"],
  ["series", "/test/series"],
  ["world-cup", "/odi/series/2023-mens-cricket-world-cup"],
  ["simulator", "/ipl/simulator"],
  ["writeup", "/writeup"],
];

for (const theme of ["dark", "light"] as const) {
  test.describe(theme, () => {
    test.use({ colorScheme: theme });

    for (const [name, path] of PAGES) {
      test(`${name} (${theme})`, async ({ page }, info) => {
        await page.goto(path);
        await page.getByRole("main").waitFor();
        await page.waitForLoadState("networkidle");
        // Let lazy charts mount before the capture.
        await page.waitForTimeout(800);
        await page.screenshot({
          path: `test-results/visual/${info.project.name}/${theme}/${name}.png`,
          fullPage: true,
          animations: "disabled",
        });
      });
    }
  });
}
