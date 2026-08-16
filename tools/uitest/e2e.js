// Viewport + console sweep over the deployed Broker site.
//
// This lived in /tmp for the whole build and was lost when tmp was cleared, so
// it lives in the repo now. It checks the two things a static dashboard can
// still get wrong: it renders at every size we claim to support, and it loads
// without a console error. Both are cheap to break and invisible in pytest.
//
//   npm install && BASE=<url> node e2e.js
//
// BASE defaults to the deployed site, so with no arguments this tests what a
// judge would actually open.

const { chromium } = require("playwright-core");

const BASE =
  process.env.BASE ||
  "https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm";

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

// The task view only reveals itself when Terac's submissionId is present, so it
// has to be requested explicitly or it never gets covered.
const PAGES = [
  { name: "company", path: "/" },
  { name: "task", path: "/?submissionId=e2e-test&taskId=t1" },
];

const failures = [];

(async () => {
  const browser = await chromium.launch({
    executablePath: EXECUTABLE,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  for (const vp of VIEWPORTS) {
    for (const pg of PAGES) {
      const label = `${pg.name}-${vp.name}`;
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

      await page.goto(BASE + pg.path, {
        waitUntil: "domcontentloaded",
        timeout: 45000,
      });
      // The ledger and checkpoints are fetched after paint.
      await page.waitForTimeout(2500);

      // Nothing may overflow horizontally. The mobile grid bug shipped twice.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 1,
      );
      if (overflow) failures.push(`${label}: horizontal overflow`);

      if (pg.name === "company") {
        // The P&L must actually render numbers, not the loading em-dash.
        const pnl = await page.evaluate(() => {
          const t = (id) => document.getElementById(id)?.textContent?.trim();
          return { rev: t("rev"), note: t("ledger-note") };
        });
        if (!pnl.rev || pnl.rev === "—")
          failures.push(`${label}: revenue never rendered`);
        else console.log(`    revenue=${pnl.rev}`);
        if (pnl.note && /loading/i.test(pnl.note))
          failures.push(`${label}: ledger stuck loading`);
      }

      if (pg.name === "task") {
        // The completion link is the only interactive element on the site and
        // it is how Terac learns the participant finished. If it is not built,
        // a paid participant cannot complete.
        const href = await page.evaluate(
          () => document.getElementById("complete")?.getAttribute("href"),
        );
        if (!href || href === "#")
          failures.push(`${label}: completion callback not built`);
        else console.log(`    callback ok -> ${href.slice(0, 78)}`);
      }

      if (errors.length) failures.push(`${label}: console ${JSON.stringify(errors)}`);
      console.log(`  ${failures.some((f) => f.startsWith(label)) ? "✗" : "✓"} ${label}`);

      await ctx.close();
    }
  }

  await browser.close();

  const total = VIEWPORTS.length * PAGES.length;
  if (failures.length) {
    console.log(`\nFAILURES (${failures.length}):`);
    for (const f of failures) console.log("  ✗ " + f);
    process.exit(1);
  }
  console.log(`\nPASS — ${total} combinations against ${BASE}`);
})().catch((e) => {
  console.error("ERROR", e.message);
  process.exit(1);
});
