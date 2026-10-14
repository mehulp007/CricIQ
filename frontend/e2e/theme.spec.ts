import { expect, test } from "@playwright/test";

const html = (page: import("@playwright/test").Page) => page.locator("html");
const DARK = /\bdark\b/;

test.describe("theme", () => {
  test.use({ colorScheme: "dark" });

  test("follows the system colour scheme until a theme is chosen", async ({ page }) => {
    await page.goto("/ipl");
    await expect(html(page)).toHaveClass(DARK);
    await page.emulateMedia({ colorScheme: "light" });
    await expect(html(page)).not.toHaveClass(DARK);
    await expect(page.getByRole("radio", { name: "System theme" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  test("a chosen theme is remembered across pages and reloads", async ({ page }) => {
    await page.goto("/ipl");
    await page.getByRole("radio", { name: "Light theme" }).click();
    await expect(html(page)).not.toHaveClass(DARK);

    await page.goto("/ipl/players");
    await expect(html(page)).not.toHaveClass(DARK);

    await page.reload();
    await expect(html(page)).not.toHaveClass(DARK);
    await expect(page.getByRole("radio", { name: "Light theme" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  test("the stored theme is on <html> before any script bundle runs", async ({ browser }) => {
    // JavaScript bundles blocked: only the inline <head> script can set the theme, so a correct
    // class here means the page never paints in the wrong theme.
    const context = await browser.newContext({ colorScheme: "dark" });
    await context.addCookies([
      { name: "criciq-theme", value: "light", url: test.info().project.use.baseURL! },
    ]);
    const page = await context.newPage();
    await page.route("**/_next/static/**/*.js", (route) => route.abort());
    await page.goto("/ipl");
    await expect(html(page)).not.toHaveClass(DARK);
    await context.close();
  });
});
