// Capture the user-manual screenshot set from the running UI (http://127.0.0.1:8123).
//   npm i playwright   # (browsers already cached if you've used playwright before)
//   python ../server.py &   &&   node capture_shots.mjs
// Writes numbered PNGs into ../docs/screenshots/. Deterministic UI → same shots every run.
import { chromium } from "playwright";
import fs from "fs";

const OUT = process.env.DATAGEN_SHOTS || new URL("../docs/screenshots/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });
const APP = process.env.DATAGEN_URL || "http://127.0.0.1:8123/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function setRange(page, sel, value) {
  await page.evaluate(({ sel, value }) => {
    const r = document.querySelector(sel);
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(r, String(value));
    r.dispatchEvent(new Event("input", { bubbles: true }));
  }, { sel, value });
  await sleep(450);
}
async function setSeed(page, v) {
  await page.evaluate((v) => {
    const el = document.querySelector("#seed");
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true }));
  }, v);
  await page.evaluate(() => document.querySelector("#gen").click());
  await sleep(450);
}
const shot = (page, name, opts = {}) => page.screenshot({ path: `${OUT}/${name}.png`, ...opts });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await page.goto(APP, { waitUntil: "networkidle" });
await sleep(700);

// 01 overview (default: dirt 0.6, link 4, ho-0)
await shot(page, "01_overview", { fullPage: true });
// 02 control bar (crop)
await shot(page, "02_controls", { clip: { x: 0, y: 52, width: 1440, height: 78 } });
// 03 clean (dirt 0) — corruption empty
await setRange(page, "#dirt", 0);
await shot(page, "03_clean", { fullPage: true });
// 04 heavy dirt (dirt 0.9)
await setRange(page, "#dirt", 0.9);
await shot(page, "04_dirty", { fullPage: true });
// 05 corruption map close-up (dirt 0.9) — crop the chips card
await page.evaluate(() => document.querySelector("#chips").closest(".card").scrollIntoView({ block: "center" }));
await sleep(300);
await shot(page, "05_corruption", { clip: await page.evaluate(() => { const r = document.querySelector("#chips").closest(".card").getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height }; }) });
// 06 link=1 literal ids → naive perfect (dirt 0)
await setRange(page, "#dirt", 0);
await setRange(page, "#link", 1);
await shot(page, "06_link1_naive_perfect", { clip: await page.evaluate(() => { const r = document.querySelector("#c-disc").getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height }; }) });
// 07 link=4 hidden → naive collapses (dirt 0)
await setRange(page, "#link", 4);
await shot(page, "07_link4_naive_collapse", { clip: await page.evaluate(() => { const r = document.querySelector("#c-disc").getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height }; }) });
// 08 cross-source hover: hover the first truth chain → throughput + shipments highlight
await setRange(page, "#dirt", 0.3);
await page.hover(".chain");
await sleep(400);
await shot(page, "08_truthchain_hover", { fullPage: true });
// 09 news feed close-up (dirt 0.9 shows garble/time flags)
await setRange(page, "#dirt", 0.9);
await page.evaluate(() => document.querySelector("#news").closest(".card").scrollIntoView({ block: "center" }));
await sleep(300);
await shot(page, "09_news", { clip: await page.evaluate(() => { const r = document.querySelector("#news").closest(".card").getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: Math.min(r.height, 900 - r.y) }; }) });
// 10 shipments table (dirt 0.9: lb + null flags)
await page.evaluate(() => document.querySelector("#ship").closest(".card").scrollIntoView({ block: "center" }));
await sleep(300);
await shot(page, "10_shipments", { clip: await page.evaluate(() => { const r = document.querySelector("#ship").closest(".card").getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: Math.min(r.height, 900 - r.y) }; }) });

await browser.close();
console.log("captured 10 screenshots →", OUT);
