import { expect, test } from "@playwright/test";

test.describe("app shell", () => {
  test("Ctrl+K searches players and opens the one chosen", async ({ page, isMobile }) => {
    test.skip(isMobile, "keyboard shortcuts are a desktop feature");
    await page.goto("/ipl");
    await page.keyboard.press("Control+K");
    const search = page.getByRole("combobox", { name: /Search pages, players/ });
    await expect(search).toBeFocused();
    await search.fill("kohli");
    const option = page.getByRole("option", { name: /Virat Kohli/ });
    await expect(option).toBeVisible();
    await option.click();
    await expect(page).toHaveURL(/\/ipl\/players\/ba607b88$/);
  });

  test("the search button opens pages by keyboard, and Escape closes it", async ({ page }) => {
    await page.goto("/ipl/matches");
    await page.getByRole("button", { name: "Search" }).click();
    const search = page.getByRole("combobox", { name: /Search pages, players/ });
    await search.fill("model ins");
    await expect(page.getByRole("option", { name: /Model Insights/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await search.press("Escape");
    await expect(search).toBeHidden();
    await page.getByRole("button", { name: "Search" }).click();
    await page.getByRole("combobox", { name: /Search pages, players/ }).fill("model ins");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/ipl\/models$/);
  });

  test("on phones the bottom bar reaches the main pages and the rest", async ({
    page,
    isMobile,
  }) => {
    test.skip(!isMobile, "the bottom bar is for phones");
    await page.goto("/bbl");
    const bar = page.getByRole("navigation", { name: "Quick" });
    await bar.getByRole("link", { name: "Players" }).click();
    await expect(page).toHaveURL(/\/bbl\/players$/);
    await expect(bar.getByRole("link", { name: "Players" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await bar.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Compare" })
      .click();
    await expect(page).toHaveURL(/\/bbl\/compare$/);
  });

  test("detail pages show where they are, from the competition down", async ({ page }) => {
    await page.goto("/ipl/players/ba607b88");
    const trail = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(trail.getByRole("link", { name: "IPL" })).toHaveAttribute("href", "/ipl");
    await trail.getByRole("link", { name: "Players" }).click();
    await expect(page).toHaveURL(/\/ipl\/players$/);
  });
});
