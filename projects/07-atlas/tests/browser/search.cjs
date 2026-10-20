"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;

async function main() {
  const base = process.env.ATLAS_BROWSER_URL;
  assert.ok(base, "Run through check_browser.py with its disposable index");
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.ATLAS_CHROMIUM_PATH || (fs.existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined),
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 1060 } });
    const page = await context.newPage();
    const errors = [];
    const external = [];
    const accessibility = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (new URL(request.url()).origin !== base) external.push(request.url());
    });
    const audit = async (state) => {
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      accessibility.push({ state, violations: result.violations.map((item) => ({ id: item.id, nodes: item.nodes.map((node) => node.target) })) });
      assert.deepEqual(result.violations, [], "accessibility violations in " + state);
    };

    await page.goto(base, { waitUntil: "networkidle" });
    await audit("desktop initial");
    await page.getByLabel("Access token", { exact: true }).fill("synthetic-reader-token");
    await page.getByLabel("Search your documents", { exact: true }).fill("recovery");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.waitForSelector(".result-card");
    assert.equal(await page.locator(".result-card").count(), 10);
    assert.equal(await page.locator("#result-count").textContent(), "23 documents");
    assert.equal(await page.locator(".result-card img").count(), 0);
    assert.ok((await page.locator(".result-snippet").first().textContent()).includes("<img"));
    await audit("desktop results");
    await page.getByRole("button", { name: "Next", exact: false }).click();
    await page.waitForFunction(() => document.getElementById("page-description").textContent === "Page 2");
    await page.getByRole("button", { name: "Read document: Recovery procedure 11", exact: true }).click();
    await page.waitForFunction(() => document.getElementById("document-text").textContent.includes("WAL recovery"));
    await audit("document dialog");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("dialog[open]").count(), 0);
    assert.ok(await page.getByRole("button", { name: "Read document: Recovery procedure 11", exact: true }).evaluate((node) => node === document.activeElement));
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await audit("mobile results");

    await page.locator("#connection > summary").click();
    await page.getByRole("button", { name: "Clear connection" }).click();
    assert.equal(await page.locator(".result-card").count(), 0);
    assert.equal(await page.locator("#token").inputValue(), "");
    assert.equal(await page.locator("#document-text").textContent(), "");
    await page.locator("#token").fill("invalid-synthetic-token");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.waitForFunction(() => document.getElementById("status").textContent.includes("not accepted"));
    assert.equal(await page.locator(".result-card").count(), 0);
    await page.locator("#token").fill("synthetic-reader-token");
    await page.locator("#query").fill("no-such-vocabulary");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.waitForFunction(() => document.getElementById("result-count").textContent === "0 documents");
    assert.ok(await page.getByRole("heading", { name: "No matching documents" }).isVisible());

    let releaseOlder;
    let markStarted;
    const started = new Promise((resolve) => { markStarted = resolve; });
    const release = new Promise((resolve) => { releaseOlder = resolve; });
    await page.route("**/search?**", async (route) => {
      if (new URL(route.request().url()).searchParams.get("q") === "older") {
        markStarted();
        await release;
        await route.fulfill({ json: { total: 0, hits: [], facets: {} } }).catch(() => {});
      } else {
        await route.continue();
      }
    });
    await page.locator("#query").fill("older");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await started;
    await page.locator("#query").fill("recovery");
    await page.evaluate(() => document.getElementById("search-form").requestSubmit());
    await page.waitForSelector(".result-card");
    releaseOlder();
    await page.waitForFunction(() => document.getElementById("status").textContent === "Results for “recovery”.");
    assert.equal(await page.locator(".result-card").count(), 10);
    await page.locator("#connection > summary").click();
    await page.locator("#token").fill("changed-synthetic-token");
    assert.equal(await page.locator(".result-card").count(), 0);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);

    const noScript = await browser.newContext({ javaScriptEnabled: false });
    const fallback = await noScript.newPage();
    await fallback.goto(base);
    assert.ok(await fallback.getByRole("button", { name: "Search", exact: true }).isDisabled());
    assert.equal(await fallback.locator("#token").getAttribute("name"), null);
    await noScript.close();
    await context.close();
    console.log(JSON.stringify({ functional: "passed", accessibility }));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
