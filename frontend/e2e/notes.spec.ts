import { expect, test } from "@playwright/test";

// Daily notes are served from the API's notes database, built from the fixture data
// (`criciq-data notes`). The 2025 IPL final ended on 3 June 2025 and is in every build.
const FINAL = "2025-06-03";
const HEADLINE = "Royal Challengers Bengaluru beat Punjab Kings by 6 runs in the IPL 2025 final";

test.describe("daily notes", () => {
  test("the list shows the latest notes and filters by competition", async ({ page }) => {
    await page.goto("/notes");
    await expect(page.getByRole("heading", { level: 1, name: "Daily notes" })).toBeVisible();
    const notes = page.getByRole("list", { name: "Notes" });
    await expect(notes.getByRole("listitem").first()).toBeVisible();
    const dates = await notes
      .locator("time")
      .evaluateAll((els) => els.map((e) => e.getAttribute("datetime") ?? ""));
    expect(dates.length).toBeGreaterThan(1);
    expect([...dates].sort().reverse()).toEqual(dates);

    await page
      .getByRole("navigation", { name: "Competition" })
      .getByRole("link", { name: "IPL" })
      .click();
    await expect(page).toHaveURL(/\/notes\?competition=ipl$/);
    await expect(notes.getByRole("link", { name: new RegExp(HEADLINE) })).toBeVisible();
    for (const card of await notes.getByRole("listitem").all()) {
      await expect(card).toContainText("IPL");
    }
  });

  test("a note opens with its items, figures and links", async ({ page }) => {
    await page.goto("/notes");
    await page.getByRole("link", { name: new RegExp(HEADLINE) }).click();
    await expect(page).toHaveURL(new RegExp(`/notes/${FINAL}$`));
    await expect(page.getByRole("heading", { level: 1, name: HEADLINE })).toBeVisible();
    await expect(page.getByText(/Data checked: data version/)).toBeVisible();
    await expect(page.getByText("Why it matters:").first()).toBeVisible();
    await expect(page.getByText("The final: it decided the IPL 2025 title.")).toBeVisible();
    await expect(page.getByText("Model estimate").first()).toBeVisible();
    await expect(page.getByRole("img", { name: /in numbers/ })).toBeVisible();
    await expect(
      page.getByText(/Written automatically from CricIQ's ball-by-ball data/),
    ).toBeVisible();
    // JSON-LD for search engines.
    const ld = await page.locator('script[type="application/ld+json"]').textContent();
    expect(JSON.parse(ld ?? "{}")).toMatchObject({ "@type": "Article", headline: HEADLINE });
  });

  test("the turning point opens the replay at its ball", async ({ page }) => {
    await page.goto(`/notes/${FINAL}`);
    await page.getByRole("link", { name: "Replay that ball" }).first().click();
    await expect(page).toHaveURL(/\/ipl\/matches\/1473511\?ball=2\.\d+$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("previous and next notes link up", async ({ page }) => {
    await page.goto(`/notes/${FINAL}`);
    const others = page.getByRole("navigation", { name: "Other notes" });
    await others.getByRole("link").first().click();
    await expect(page).not.toHaveURL(new RegExp(`/notes/${FINAL}$`));
    await page
      .getByRole("navigation", { name: "Other notes" })
      .getByRole("link", { name: /3 June 2025/ })
      .click();
    await expect(page).toHaveURL(new RegExp(`/notes/${FINAL}$`));
  });

  test("the day's figures download as a PNG", async ({ page }) => {
    await page.goto(`/notes/${FINAL}`);
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download PNG" }).click();
    expect((await download).suggestedFilename()).toBe(`criciq-notes-${FINAL}.png`);
  });

  test("the RSS feed is valid XML", async ({ page, request }) => {
    const response = await request.get("/notes/feed.xml");
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/rss+xml");
    const xml = await response.text();
    await page.goto("/notes");
    const found = await page.evaluate((text) => {
      const doc = new DOMParser().parseFromString(text, "application/xml");
      return {
        broken: doc.querySelector("parsererror") !== null,
        items: doc.querySelectorAll("item").length,
        titles: Array.from(doc.querySelectorAll("item > title")).map((t) => t.textContent),
      };
    }, xml);
    expect(found.broken).toBe(false);
    expect(found.items).toBeGreaterThan(0);
    expect(found.titles).toContain(HEADLINE);
    await expect(page.locator('link[rel="alternate"][type="application/rss+xml"]')).toHaveAttribute(
      "href",
      /\/notes\/feed\.xml$/,
    );
  });

  test("a page past the last note says so", async ({ page }) => {
    await page.goto("/notes?before=2000-01-01");
    await expect(page.getByText("No notes yet")).toBeVisible();
  });

  test("the home pages show the latest notes", async ({ page }) => {
    await page.goto("/");
    const latest = page.getByRole("region", { name: "Latest notes" });
    await expect(
      latest.getByRole("link").filter({ hasText: "Read the note" }).first(),
    ).toBeVisible();
    await page.goto("/ipl");
    const ipl = page.getByRole("region", { name: "Latest from the IPL" });
    await expect(ipl.getByRole("link", { name: new RegExp(HEADLINE) })).toBeVisible();
  });
});
