import { expect, test, type Page } from "@playwright/test";

// Chart Studio is served from the API. Virat Kohli (ba607b88) and Rohit Sharma (b8a55852)
// played the IPL matches in every build of the data, including the test fixtures.
const KOHLI = "ba607b88";
const ROHIT = "b8a55852";

const TEMPLATES = [
  "Player profile",
  "Compare players",
  "Leaderboard",
  "Timeline",
  "Batting explorer",
  "Bowling explorer",
  "Team form",
  "Grounds",
  "Season recap",
  "Match card",
  "Blank canvas",
];

function chart(page: Page) {
  return page.getByRole("tabpanel", { name: "Visual" }).locator("svg[data-export-width]");
}

// The page's own error message (Next's route announcer is an alert too).
function problem(page: Page) {
  return page.getByRole("main").getByRole("alert");
}

async function settled(page: Page) {
  await expect(page.getByRole("status").filter({ hasText: "Updating" })).toHaveCount(0);
  await expect(chart(page)).toBeVisible();
}

test.describe("chart studio", () => {
  test("every template draws a chart", async ({ page }) => {
    await page.goto("/ipl/studio");
    await expect(page.getByRole("heading", { level: 1, name: "Chart Studio" })).toBeVisible();
    const templates = page.getByRole("group", { name: "Templates" });
    for (const name of TEMPLATES) {
      await templates.getByRole("button", { name, exact: true }).click();
      await expect(templates.getByRole("button", { name, exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await settled(page);
      await expect(problem(page)).toHaveCount(0);
      await expect(chart(page).locator("text").first()).toBeVisible();
    }
    await expect(page).toHaveURL(/t=blank|\/ipl\/studio$/);
  });

  test("downloads the chart as PNG and SVG, and its figures as CSV", async ({ page }) => {
    await page.goto("/ipl/studio?t=leaderboard");
    await settled(page);
    const exports = page.getByRole("group", { name: "Export" });
    for (const [button, extension] of [
      ["PNG", "png"],
      ["SVG", "svg"],
      ["CSV", "csv"],
    ] as const) {
      const download = page.waitForEvent("download");
      await exports.getByRole("button", { name: button, exact: true }).click();
      const file = await download;
      expect(file.suggestedFilename()).toBe(`ipl-runs-by-player.${extension}`);
      const path = await file.path();
      expect(path).toBeTruthy();
    }
  });

  test("the SVG stands alone and the CSV holds the figures", async ({ page }) => {
    await page.goto("/ipl/studio?t=leaderboard");
    await settled(page);
    const exports = page.getByRole("group", { name: "Export" });

    let download = page.waitForEvent("download");
    await exports.getByRole("button", { name: "SVG", exact: true }).click();
    const svg = await (await download).createReadStream();
    const markup = await new Promise<string>((resolve) => {
      let text = "";
      svg.on("data", (chunk: Buffer) => (text += chunk.toString("utf8")));
      svg.on("end", () => resolve(text));
    });
    expect(markup).toContain('width="1200"');
    expect(markup).not.toContain("var(--");
    expect(markup).toContain("Data: Cricsheet");
    expect(markup).toContain("@font-face");
    const wellFormed = await page.evaluate(
      (text) =>
        new DOMParser().parseFromString(text, "image/svg+xml").querySelector("parsererror") ===
        null,
      markup,
    );
    expect(wellFormed).toBe(true);

    download = page.waitForEvent("download");
    await exports.getByRole("button", { name: "CSV", exact: true }).click();
    const csv = await (await download).createReadStream();
    const text = await new Promise<string>((resolve) => {
      let body = "";
      csv.on("data", (chunk: Buffer) => (body += chunk.toString("utf8")));
      csv.on("end", () => resolve(body));
    });
    expect(text.split("\r\n")[0]).toBe("Rank,Player,Runs,balls faced");
    expect(text.split("\r\n").length).toBeGreaterThan(3);
  });

  test("a link rebuilds the same chart", async ({ page, context, browserName }) => {
    test.skip(browserName !== "chromium", "clipboard permissions are Chromium's");
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.goto(`/ipl/studio?t=compare&p=${KOHLI},${ROHIT}`);
    await settled(page);
    await page.getByRole("button", { name: "Paper", exact: true }).click();
    await page.getByLabel("Title", { exact: true }).fill("Kohli and Rohit");
    await expect(page).toHaveURL(/theme=paper/);
    await expect(page).toHaveURL(/title=Kohli\+and\+Rohit/);
    await page.getByRole("button", { name: "Copy link" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Link copied." })).toBeVisible();
    const link = await page.evaluate(() => navigator.clipboard.readText());
    const before = await chart(page).textContent();

    const other = await context.newPage();
    await other.goto(link);
    await settled(other);
    await expect(chart(other).locator("title").first()).toHaveText("Kohli and Rohit");
    await expect(other.getByRole("list", { name: "Chosen players" })).toContainText("Virat Kohli");
    expect(await chart(other).textContent()).toBe(before);
    await expect(chart(other).locator("rect").first()).toHaveAttribute("fill", "#f7f3ea");
  });

  test("players can be searched, added and removed", async ({ page }) => {
    await page.goto("/ipl/studio?t=compare");
    await settled(page);
    await page.getByRole("combobox", { name: /Players/ }).fill("Kohli");
    await page.getByRole("option", { name: /Kohli/ }).first().click();
    await expect(page).toHaveURL(new RegExp(`p=${KOHLI}`));
    const chosen = page.getByRole("list", { name: "Chosen players" });
    await expect(chosen).toContainText("Kohli");
    await settled(page);
    await page.getByRole("tab", { name: "Table" }).click();
    await expect(page.getByRole("region", { name: "Chart figures" })).toContainText("Kohli");
    await page.getByRole("button", { name: /Remove .*Kohli/ }).click();
    await expect(page).not.toHaveURL(/p=/);
  });

  test("shows the query and a table of the figures", async ({ page }) => {
    await page.goto("/ipl/studio?t=batting");
    await settled(page);
    await page.getByRole("tab", { name: "SQL" }).click();
    const query = page.getByRole("region", { name: "Query" });
    await expect(query).toContainText("FROM player_batting_innings");
    await expect(query).toContainText("LIMIT ?");
    await page.getByRole("tab", { name: "Table" }).click();
    const table = page.getByRole("region", { name: "Chart figures" });
    await expect(table.getByRole("columnheader", { name: "Strike rate" })).toBeVisible();
    await table.getByRole("link").first().click();
    await expect(page).toHaveURL(/\/ipl\/players\/[0-9a-f]{8}$/);
  });

  test("a filter that leaves nothing says so", async ({ page }) => {
    await page.goto("/ipl/studio?t=leaderboard&min=1000000");
    await expect(page.getByText("Nothing qualifies")).toBeVisible();
    await expect(page.getByRole("button", { name: "PNG", exact: true })).toBeDisabled();
  });

  test("a bad link falls back to the defaults", async ({ page }) => {
    await page.goto("/ipl/studio?d=matches&m=drop,table&g=nope&chart=pie&theme=neon&n=999");
    await settled(page);
    await expect(problem(page)).toHaveCount(0);
    await expect(chart(page).locator("title").first()).toHaveText("IPL: runs by player");
  });

  test("works from the keyboard", async ({ page }) => {
    await page.goto("/ipl/studio");
    await settled(page);
    const leaderboard = page.getByRole("button", { name: "Leaderboard", exact: true });
    await leaderboard.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/t=leaderboard/);
    const sixes = page.getByRole("checkbox", { name: "6s" });
    await sixes.focus();
    await page.keyboard.press("Space");
    await expect(page).toHaveURL(/m=runs%2Csixes/);
    const paper = page.getByRole("button", { name: "Paper", exact: true });
    await paper.focus();
    await page.keyboard.press("Enter");
    await expect(paper).toHaveAttribute("aria-pressed", "true");
    await settled(page);
    await page.getByRole("tab", { name: "Visual" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Table" })).toHaveAttribute("aria-selected", "true");
  });

  test("player pages, Compare and record lists open the studio prefilled", async ({ page }) => {
    await page.goto(`/ipl/players/${KOHLI}`);
    await page.getByRole("link", { name: "Make a chart" }).click();
    await expect(page).toHaveURL(new RegExp(`/ipl/studio\\?t=profile&p=${KOHLI}`));
    await settled(page);
    await expect(chart(page).locator("title").first()).toHaveText(/Virat Kohli in the IPL/);

    await page.goto(`/ipl/compare?a=${KOHLI}&b=${ROHIT}`);
    await page.getByRole("link", { name: "Make a chart of these two" }).click();
    await expect(page).toHaveURL(/t=compare/);
    await settled(page);

    await page.goto("/ipl/records/most-wickets");
    await page.getByRole("link", { name: "Make a chart" }).click();
    await expect(page).toHaveURL(/t=leaderboard&d=bowling&m=wickets/);
    await settled(page);
    await expect(chart(page).locator("title").first()).toHaveText("IPL: wickets by player");
  });

  test("Tests have their own phases and the match card", async ({ page }) => {
    await page.goto("/test/studio?d=phase_bowling&m=wickets&g=phase");
    await settled(page);
    await page.getByRole("tab", { name: "Table" }).click();
    const table = page.getByRole("region", { name: "Chart figures" });
    await expect(table).toContainText("New ball");
    await expect(table).toContainText("Second new ball");
    await page.goto("/test/studio?t=match");
    await settled(page);
    await expect(chart(page).locator("title").first()).toHaveText(/ v /);
  });
});
