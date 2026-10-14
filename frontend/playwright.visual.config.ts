import { defineConfig, devices } from "@playwright/test";

/**
 * Screenshots of the key pages in both themes on desktop and mobile, for reviewing the design:
 *   pnpm visual          (against http://localhost:3000; E2E_BASE_URL to change)
 * They are written to test-results/visual/ and compared by eye, not asserted, so this never
 * runs in CI.
 */
export default defineConfig({
  testDir: "./e2e-visual",
  testMatch: "**/*.visual.ts",
  timeout: 90_000,
  fullyParallel: true,
  reporter: "list",
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000" },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
