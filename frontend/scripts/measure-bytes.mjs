// Bytes a phone downloads for the kiosk link, each download counted once (Resource Timing transferSize: compressed,
// with headers; 0 for files served from the browser's cache). Run against a production build, not `next dev`:
//   npm run build && npx next start -p 3010        (API running, e.g. on :8030)
//   node scripts/measure-bytes.mjs http://localhost:3010/k/MANIKPUR
// Needs Playwright, which is not a project dependency: npm i --no-save playwright && npx playwright install chromium.
// Figures: docs/EVALUATION.md.
import { chromium } from "playwright";

const URL_ = process.argv[2] || "http://localhost:3010/k/MANIKPUR";
const kb = (n) => (n / 1024).toFixed(1) + " KB";

(async () => {
  const b = await chromium.launch({ headless: true });
  const ctx = await b.newContext();
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: "networkidle" });
  await page.waitForTimeout(7000); // the intake wizard is fetched and kept for offline use after the page settles
  // Page requests that went straight to the network, plus everything the service worker fetched (later page requests
  // pass through it, so they are counted there and not twice).
  const direct = await page.evaluate(() =>
    [...performance.getEntriesByType("navigation"), ...performance.getEntriesByType("resource")].filter((e) => !e.workerStart).reduce((a, e) => a + e.transferSize, 0));
  const sw = ctx.serviceWorkers()[0];
  const viaWorker = sw ? await sw.evaluate(() => performance.getEntriesByType("resource").reduce((a, e) => a + e.transferSize, 0)) : 0;
  console.log(`first visit: ${kb(direct + viaWorker)} (page ${kb(direct)}, through the service worker ${kb(viaWorker)})${sw ? "" : " — no service worker: is this a production build?"}`);

  await ctx.setOffline(true);
  await page.reload({ waitUntil: "load" });
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: /^Start$/ }).click();
  await page.waitForTimeout(2000);
  console.log("opens again with no network, intake wizard included:", /Your permission/.test(await page.locator("main").innerText()));
  await b.close();
})();
