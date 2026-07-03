// Drive the live datagen UI (http://127.0.0.1:8123) through the walkthrough, paced to the narration scene
// durations in scenes.json, and record a webm. Then mux.py overlays master.wav + burns subs.srt.
//   npm i playwright  &&  python ../server.py &  &&  node record.mjs
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const DEMO = process.env.DATAGEN_DEMO || path.dirname(fileURLToPath(import.meta.url));
const APP = process.env.DATAGEN_URL || "http://127.0.0.1:8123/";
const plan = JSON.parse(fs.readFileSync(path.join(DEMO, "scenes.json"), "utf-8"));
const VIDEO_DIR = path.join(DEMO, "video");
fs.rmSync(VIDEO_DIR, { recursive: true, force: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function setRange(page, sel, value) {
  await page.evaluate(({ sel, value }) => {
    const r = document.querySelector(sel);
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(r, String(value)); r.dispatchEvent(new Event("input", { bubbles: true }));
  }, { sel, value });
}
async function sweep(page, sel, from, to, steps, stepMs) {
  for (let s = 0; s <= steps; s++) { await setRange(page, sel, from + ((to - from) * s) / steps); await sleep(stepMs); }
}
async function seedTo(page, v) {
  await page.evaluate((v) => {
    const el = document.querySelector("#seed");
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    set.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true }));
    document.querySelector("#gen").click();
  }, v);
}
const scrollTo = (page, sel) => page.evaluate((s) => document.querySelector(s)?.scrollIntoView({ behavior: "smooth", block: "center" }), sel);
const cardOf = (id) => `#${id}`; // cards referenced by an inner id's closest .card handled in-page
async function scrollCard(page, innerId) {
  await page.evaluate((id) => { const el = document.getElementById(id); (el?.closest(".card") || el)?.scrollIntoView({ behavior: "smooth", block: "center" }); }, innerId);
}

// action key → function (page, durMs). Each should consume ~durMs.
const actions = {
  intro: async (p) => { await page0(p); await scrollTo(p, "header"); },
  problem: async (p) => { await scrollTo(p, ".controls"); },
  overview: async (p, d) => { await scrollTo(p, "#tw"); await sleep(d * 0.5); await scrollTo(p, "header"); },
  chain: async (p) => { await scrollCard(p, "chain"); },
  truth_first: async (p) => { await scrollTo(p, "#c-disc"); },
  determinism: async (p) => { await scrollTo(p, "header"); await seedTo(p, "ho-0"); await sleep(400); await seedTo(p, "ho-0"); },
  dirt_up: async (p, d) => { await setRange(p, "#dirt", 0); await scrollCard(p, "chips"); await sweep(p, "#dirt", 0, 0.9, 18, Math.max(90, (d * 0.9) / 18)); },
  corruption_map: async (p) => { await setRange(p, "#dirt", 0.9); await scrollCard(p, "chips"); },
  link_sweep: async (p, d) => { await setRange(p, "#dirt", 0); await scrollTo(p, "#c-disc"); await sweep(p, "#link", 1, 5, 12, Math.max(120, (d * 0.85) / 12)); },
  disc: async (p) => { await scrollTo(p, "#c-disc"); },
  throughput: async (p) => { await setRange(p, "#dirt", 0.3); await scrollCard(p, "tw"); },
  hover: async (p, d) => { await scrollCard(p, "chain"); await p.hover(".chain"); await sleep(d * 0.6); },
  news_ships: async (p, d) => { await scrollCard(p, "news"); await sleep(d * 0.5); await scrollCard(p, "ship"); },
  seed: async (p, d) => { await scrollTo(p, ".controls"); await seedTo(p, "ho-5"); await sleep(d * 0.45); await seedTo(p, "ho-0"); },
  cli: async (p) => { await setRange(p, "#dirt", 0.6); await setRange(p, "#link", 4); await scrollTo(p, "header"); },
  honest: async (p, d) => { await scrollCard(p, "chips"); await sleep(d * 0.5); await scrollTo(p, "#tw"); },
  outro: async (p) => { await scrollTo(p, "header"); },
};
async function page0(p) { await setRange(p, "#dirt", 0.6); await setRange(p, "#link", 4); await seedTo(p, "ho-0"); }

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1,
  recordVideo: { dir: VIDEO_DIR, size: { width: 1440, height: 900 } } });
const page = await ctx.newPage();
await page.goto(APP, { waitUntil: "networkidle" });
await page0(page);
await sleep(plan.lead * 1000);            // match the narration lead-in silence

for (const sc of plan.scenes) {
  const durMs = sc.dur * 1000, t0 = Date.now();
  const fn = actions[sc.act] || (async () => {});
  try { await fn(page, durMs); } catch (e) { console.warn("action", sc.act, "failed:", e.message); }
  const spent = Date.now() - t0;
  if (spent < durMs) await sleep(durMs - spent);   // pad to the narration duration
  await sleep(sc.gap * 1000);                        // inter-scene gap
}
await sleep(plan.tail * 1000);

await ctx.close();  // finalizes the webm
await browser.close();
const webm = fs.readdirSync(VIDEO_DIR).find((f) => f.endsWith(".webm"));
console.log("recorded", path.join(VIDEO_DIR, webm));
