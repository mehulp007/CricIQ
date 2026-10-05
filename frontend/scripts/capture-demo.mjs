// Capture README screenshots and demo-GIF frames from a running CricIQ site.
//
//   node scripts/capture-demo.mjs [baseUrl]    (default: http://localhost:3000)
//
// Writes PNGs to ../docs/images/ and the demo GIF's frames to ../docs/images/frames/
// (named <order>-<milliseconds to show>.png).
// Assemble the GIF with: uv run --with pillow python scripts/make_gif.py
import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const baseUrl = process.argv[2] ?? "http://localhost:3000";
const here = path.dirname(fileURLToPath(import.meta.url));
const images = path.resolve(here, "../../docs/images");
const frames = path.join(images, "frames");

await rm(frames, { recursive: true, force: true });
await mkdir(frames, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 1,
});

await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "overview.png") });

await page.goto(`${baseUrl}/matches`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "explorer.png") });

await page.goto(`${baseUrl}/models`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "models.png") });

// Scroll so an element sits just below the sticky top bar.
async function scrollTo(locator, offset = 80) {
  await locator.evaluate((el, gap) => {
    window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - gap);
  }, offset);
}

await page.goto(`${baseUrl}/players/ba607b88`, { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(images, "player.png") });

await page.goto(`${baseUrl}/matchups?batter=ba607b88&bowler=462411b3`, {
  waitUntil: "networkidle",
});
await scrollTo(page.getByRole("heading", { name: "Three ways to read the record" }));
await page.screenshot({ path: path.join(images, "matchup.png") });

await page.goto(`${baseUrl}/compare?a=ba607b88&b=740742ef`, { waitUntil: "networkidle" });
await scrollTo(page.getByRole("heading", { name: "Batting side by side" }));
await page.screenshot({ path: path.join(images, "compare.png") });

await page.goto(`${baseUrl}/teams?season=2019`, { waitUntil: "networkidle" });
await scrollTo(page.getByRole("heading", { name: "2019 league table" }));
await page.screenshot({ path: path.join(images, "teams.png") });

await page.goto(`${baseUrl}/teams/h2h?a=MI&b=KKR`, { waitUntil: "networkidle" });
await scrollTo(page.getByRole("heading", { name: "The record" }), 96);
await page.screenshot({ path: path.join(images, "h2h.png") });

await page.goto(`${baseUrl}/players/462411b3`, { waitUntil: "networkidle" });
await scrollTo(page.getByRole("heading", { name: "CricIQ Ratings" }));
await page.screenshot({ path: path.join(images, "ratings.png") });

// The 2019 final, from the start of the last over of the chase.
await page.goto(`${baseUrl}/matches/1181768`, { waitUntil: "networkidle" });
await page.locator("[data-replay-ready]").waitFor();
await page.getByRole("combobox", { name: "Jump to over" }).click();
await page.getByRole("option", { name: "CSK · over 19" }).click();
await page
  .getByRole("button", { name: "Pause" })
  .or(page.getByRole("button", { name: "Play" }))
  .first()
  .waitFor();
await page.mouse.click(5, 5); // move focus off the dropdown

for (let i = 0; i < 16; i++) {
  const atEnd = await page
    .getByRole("region", { name: "Scoreboard" })
    .getByText(/won by/)
    .count();
  if (atEnd) break;
  await page.getByRole("button", { name: "Next ball" }).click();
  await page.waitForTimeout(150);
}
await page.waitForTimeout(800); // let the win probability bar settle
await page.screenshot({ path: path.join(images, "replay.png") });

// One ball earlier: CSK need two off the last ball, with the pressure chart open.
await page.getByRole("button", { name: "Previous ball" }).click();
await page.getByRole("tab", { name: "Pressure" }).click();
await page.waitForTimeout(400);
await page.screenshot({ path: path.join(images, "pressure.png") });

await page.getByRole("tab", { name: "Scorecard" }).click();
await page.screenshot({ path: path.join(images, "scorecard.png") });

// What if Chennai had ten more runs with nine balls left?
await page.goto(`${baseUrl}/matches/1181768`, { waitUntil: "networkidle" });
await page.locator("[data-replay-ready]").waitFor();
await page.getByRole("button", { name: "Jump to end" }).click();
for (let i = 0; i < 9; i++) await page.getByRole("button", { name: "Previous ball" }).click();
const whatIf = page.getByRole("region", { name: "What if?" });
await whatIf.getByRole("button", { name: "Add 10 runs" }).click();
await whatIf.getByRole("button", { name: "Simulate the what-if" }).click();
await whatIf.getByText(/win chance/).waitFor({ timeout: 60_000 });
await scrollTo(whatIf, 120);
await page.screenshot({ path: path.join(images, "whatif.png") });

await page.goto(`${baseUrl}/simulator`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Simulate 10,000 matches/ }).click();
await page.getByRole("heading", { name: "Who wins" }).waitFor({ timeout: 60_000 });
await page.waitForTimeout(500);
await scrollTo(page.getByRole("heading", { name: "Who wins" }));
await page.mouse.move(5, 5);
await page.screenshot({ path: path.join(images, "simulator.png") });

await page.goto(`${baseUrl}/lab/pressure`, { waitUntil: "networkidle" });
await scrollTo(page.getByRole("heading", { name: "Does leverage work?" }));
await page.screenshot({ path: path.join(images, "lab.png") });

// The README's demo GIF: the last over of the 2019 final, then a tour of every section.
let frameNo = 0;
async function frame(ms) {
  await page.mouse.move(5, 5);
  const name = `${String(frameNo++).padStart(3, "0")}-${ms}.png`;
  await page.screenshot({ path: path.join(frames, name) });
}

await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
await frame(1800);
await page.goto(`${baseUrl}/matches/1181768`, { waitUntil: "networkidle" });
await page.locator("[data-replay-ready]").waitFor();
await page.getByRole("combobox", { name: "Jump to over" }).click();
await page.getByRole("option", { name: "CSK · over 19" }).click();
await page.mouse.click(5, 5);
for (let i = 0; i < 16; i++) {
  const atEnd = await page
    .getByRole("region", { name: "Scoreboard" })
    .getByText(/won by/)
    .count();
  await page.waitForTimeout(atEnd ? 800 : 150);
  await frame(atEnd ? 2200 : 650);
  if (atEnd) break;
  await page.getByRole("button", { name: "Next ball" }).click();
}
const tour = [
  ["/players/ba607b88", 1700],
  ["/matchups?batter=ba607b88&bowler=462411b3", 1700],
  ["/compare?a=ba607b88&b=740742ef", 1700],
  ["/teams?season=2019", 1700],
];
for (const [url, ms] of tour) {
  await page.goto(`${baseUrl}${url}`, { waitUntil: "networkidle" });
  await frame(ms);
}
await page.goto(`${baseUrl}/simulator?season=2019&a=MI&b=CSK`, { waitUntil: "networkidle" });
await frame(1500);
await page.getByRole("button", { name: /Simulate 10,000 matches/ }).click();
await page.getByRole("heading", { name: "Who wins" }).waitFor({ timeout: 90_000 });
await page.waitForTimeout(500);
await scrollTo(page.getByRole("heading", { name: "Who wins" }));
await frame(2200);
for (const [url, ms] of [
  ["/lab", 1700],
  ["/models", 2400],
]) {
  await page.goto(`${baseUrl}${url}`, { waitUntil: "networkidle" });
  await frame(ms);
}

await browser.close();
console.log(`saved screenshots to ${images}`);
