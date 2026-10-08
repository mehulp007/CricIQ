import { expect, test } from "@playwright/test";

test.describe("model insights overview", () => {
  test("sets every model against its baseline and links to its tab", async ({ page }) => {
    await page.goto("/ipl/models");
    await expect(page.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
    const results = page.getByRole("region", { name: /Every model, tested once on/ });
    await expect(results.getByRole("row")).toHaveCount(6);
    await expect(results).toContainText("coin flip");
    const splits = page.getByRole("region", { name: "Which seasons each model saw" });
    await expect(splits.getByRole("img")).toHaveCount(5);
    await expect(splits.getByRole("img").first()).toHaveAttribute("aria-label", /Tested once on/);
    await expect(
      page.getByRole("region", { name: "Custom metrics, put to the test" }).getByRole("link"),
    ).toHaveCount(4);

    await results.getByRole("link", { name: "Score projection" }).click();
    await expect(page).toHaveURL(/tab=score-projection/);
    await expect(page.getByRole("tab", { name: "Score projection", selected: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Does the 90% line mean 90%?" })).toBeVisible();
  });
});

test.describe("write-up", () => {
  test("is linked from the sidebar and tells the story with live numbers", async ({
    page,
    isMobile,
  }) => {
    await page.goto("/about");
    if (isMobile) await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("navigation", { name: "Secondary" })
      .getByRole("link", { name: "The write-up" })
      .click();
    await expect(page).toHaveURL(/\/writeup$/);
    await expect(page.getByRole("heading", { level: 1, name: "Building CricIQ" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "A simulator that admits a coin flip" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Each kind of cricket learns from its own matches" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "A Test is not a long T20" })).toBeVisible();
    await expect(page.getByRole("figure")).toHaveCount(2);
    await expect(page.getByRole("table")).toHaveCount(4);
    await expect(page.getByRole("article")).toContainText("of totals");
    await expect(page.getByRole("article")).toContainText("Men's Tests");
  });
});
