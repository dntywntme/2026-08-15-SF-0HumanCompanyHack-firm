// Viewport + console sweep over both deployed sites.
//
// This lived in /tmp for the whole build and was lost when tmp was cleared, so
// it lives in the repo now. It checks the things a static dashboard can still
// get wrong: it renders at every size we claim to support, it loads without a
// console error, and the numbers it exists to show actually arrive.
//
//   npm install && node e2e.js
//   BASE=<url> CLIENT_BASE=<url> node e2e.js
//
// Both bases default to the deployed sites, so with no arguments this tests
// what a judge would actually open.

const { chromium } = require("playwright-core");

const BASE =
  process.env.BASE ||
  "https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm";
const CLIENT_BASE =
  process.env.CLIENT_BASE ||
  "https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-client";

// Chromium is preinstalled in the devcontainer; playwright-core does not fetch
// a browser of its own, which is why this pins an executable path.
const EXECUTABLE = process.env.CHROMIUM || "/usr/bin/chromium";

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "tablet-portrait", width: 820, height: 1180 },
  { name: "tablet-landscape", width: 1180, height: 820 },
  { name: "phone-portrait", width: 390, height: 844, mobile: true },
  { name: "phone-landscape", width: 844, height: 390, mobile: true },
];

const text = (page, id) =>
  page.evaluate(
    (i) => document.getElementById(i)?.textContent?.trim() ?? null,
    id,
  );

// ── Per-page assertions ───────────────────────────────────────────────────────
// Each returns a list of failure strings. Keeping them separate is what stops
// the sweep itself from becoming the most complicated thing in the repo.

async function checkCompany(page, log) {
  const fail = [];
  // The P&L must render numbers, not the loading em-dash.
  const rev = await text(page, "rev");
  const note = await text(page, "ledger-note");
  if (!rev || rev === "—") fail.push("revenue never rendered");
  else log(`revenue=${rev}`);
  if (note && /loading/i.test(note)) fail.push("ledger stuck loading");

  // The run is manifest-driven: if the manifest and the checkpoints disagree,
  // the stage strip silently empties and nobody notices.
  const stages = await page.evaluate(
    () =>
      [...document.querySelectorAll("#stages .chip")].map((c) => c.textContent),
  );
  if (!stages.length) fail.push("no stages rendered");
  else log(`stages=${stages.join(",")}`);

  // The before/after is the event's mandatory deliverable. It is not optional.
  const after = await text(page, "after");
  if (!after) fail.push("before/after panel never rendered");
  return fail;
}

async function checkTask(page, log) {
  // The completion link is the only interactive element on the site and it is
  // how Terac learns the participant finished. If it is not built, a paid
  // participant cannot complete.
  const href = await page.evaluate(() =>
    document.getElementById("complete")?.getAttribute("href"),
  );
  if (!href || href === "#") return ["completion callback not built"];
  log(`callback ok -> ${href.slice(0, 78)}`);
  return [];
}

async function checkClient(page, log) {
  const fail = [];
  const verdict = await text(page, "verdict");
  if (!verdict) fail.push("verdict never rendered");
  else log(`verdict=${verdict.slice(0, 60)}`);

  // The cross-repo claim: the client page reads Broker's published ledger and
  // reconciles against it. If that fetch fails the page still renders, which is
  // exactly why it needs an assertion rather than an eyeball.
  const reconciled = await page.evaluate(() =>
    document.body.innerText.includes("ledger shows it"),
  );
  if (!reconciled) fail.push("did not reconcile against Broker's ledger");
  return fail;
}

const PAGES = [
  { name: "company", url: () => `${BASE}/`, check: checkCompany },
  {
    name: "task",
    url: () => `${BASE}/?submissionId=e2e-test&taskId=t1`,
    check: checkTask,
  },
  { name: "client", url: () => `${CLIENT_BASE}/`, check: checkClient },
];

// ── The sweep ─────────────────────────────────────────────────────────────────

async function sweepOne(browser, vp, pg) {
  const label = `${pg.name}-${vp.name}`;
  const log = (m) => console.log(`    ${m}`);
  const ctx = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    isMobile: !!vp.mobile,
    hasTouch: !!vp.mobile,
  });
  const page = await ctx.newPage();

  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));

  try {
    await page.goto(pg.url(), { waitUntil: "domcontentloaded", timeout: 45000 });
    // The ledger and checkpoints are fetched after paint.
    await page.waitForTimeout(2500);

    const fail = [];
    // Nothing may overflow horizontally. The mobile grid bug shipped twice.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    if (overflow) fail.push("horizontal overflow");
    fail.push(...(await pg.check(page, log)));
    if (errors.length) fail.push(`console ${JSON.stringify(errors)}`);

    console.log(`  ${fail.length ? "✗" : "✓"} ${label}`);
    return fail.map((f) => `${label}: ${f}`);
  } finally {
    await ctx.close();
  }
}

(async () => {
  const browser = await chromium.launch({
    executablePath: EXECUTABLE,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const failures = [];

  try {
    for (const vp of VIEWPORTS) {
      for (const pg of PAGES) {
        failures.push(...(await sweepOne(browser, vp, pg)));
      }
    }
  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.log(`\nFAILURES (${failures.length}):`);
    for (const f of failures) console.log("  ✗ " + f);
    process.exit(1);
  }
  const total = VIEWPORTS.length * PAGES.length;
  console.log(`\nPASS — ${total} combinations against ${BASE} and ${CLIENT_BASE}`);
})().catch((e) => {
  console.error("ERROR", e.message);
  process.exit(1);
});
