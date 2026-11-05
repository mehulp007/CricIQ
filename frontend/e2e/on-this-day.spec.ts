import { expect, test } from "@playwright/test";

// The 2019 IPL final (12 May 2019) is in every build of the data, fixtures included.
test.describe("on this day", () => {
  test("a date shows its standout match and every other one", async ({ page }) => {
    await page.goto("/on-this-day/may-12");
    await expect(
      page.getByRole("heading", { level: 1, name: "On this day: 12 May" }),
    ).toBeVisible();
    const standout = page.getByRole("region", { name: "The day's standout match" });
    await expect(standout.getByRole("article")).toContainText("Mumbai Indians");
    await expect(standout).toContainText("IPL");
    await expect(standout.getByRole("link", { name: "Scorecard and replay" })).toHaveAttribute(
      "href",
      /\/ipl\/matches\/\d+$/,
    );
  });

  test("the days either side and the date picker move through the year", async ({ page }) => {
    await page.goto("/on-this-day/may-12");
    await page
      .getByRole("navigation", { name: "Dates" })
      .getByRole("link", { name: "11 May", exact: true })
      .click();
    await expect(page).toHaveURL(/\/on-this-day\/may-11$/);
    await page.getByRole("combobox", { name: "Month" }).click();
    await page.getByRole("option", { name: "February" }).click();
    await expect(page).toHaveURL(/\/on-this-day\/february-11$/);
    await page.getByRole("combobox", { name: "Day" }).click();
    await page.getByRole("option", { name: "29", exact: true }).click();
    await expect(page).toHaveURL(/\/on-this-day\/february-29$/);
  });

  test("filters narrow the day to a competition", async ({ page }) => {
    await page.goto("/on-this-day/may-12?competition=test");
    await expect(page.getByText("None match these filters")).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page).toHaveURL(/\/on-this-day\/may-12$/);
    await expect(page.getByRole("region", { name: "The day's standout match" })).toBeVisible();
  });

  test("a day without matches says so, and an impossible date is not found", async ({ page }) => {
    await page.goto("/on-this-day/december-25");
    await expect(page.getByText("No matches on 25 December")).toBeVisible();
    await page.goto("/on-this-day/november-31");
    await expect(page.getByRole("heading", { name: "This page doesn't exist." })).toBeVisible();
  });

  test("today's page lands on the visitor's own date", async ({ page }) => {
    await page.goto("/on-this-day");
    await expect(
      page.getByRole("heading", { level: 1, name: /^On this day: \d+ \w+$/ }),
    ).toBeVisible();
    const local = await page.evaluate(() =>
      new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long" }),
    );
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(`On this day: ${local}`);
  });

  test("each date has a card image to share", async ({ request }) => {
    const card = await request.get("/on-this-day/may-12/card");
    expect(card.status()).toBe(200);
    expect(card.headers()["content-type"]).toContain("image/png");
    expect((await request.get("/on-this-day/june-31/card")).status()).toBe(404);
  });

  test("the widget's data route checks its date", async ({ request }) => {
    const day = await request.get("/api/on-this-day?date=may-12&competition=ipl&limit=2");
    expect(day.status()).toBe(200);
    const body = await day.json();
    expect(body.entries.length).toBeGreaterThan(0);
    expect(body.entries[0].competition).toBe("ipl");
    expect((await request.get("/api/on-this-day?date=may-32")).status()).toBe(422);
    expect((await request.get("/api/on-this-day?date=may-1&competition=xyz")).status()).toBe(404);
  });

  test("the sidebar links to it", async ({ page, isMobile }) => {
    await page.goto("/about");
    // On a phone the sidebar's links are behind the menu button.
    if (isMobile) await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("navigation", { name: "Secondary" })
      .getByRole("link", { name: "On this day" })
      .click();
    await expect(page).toHaveURL(/\/on-this-day/);
  });
});
