/* DOM regression tests for src/App.tsx — run with: node scripts/test-app-dom.cjs
 *
 * Covers the App-level behaviour that scripts/test-guardrail.cjs cannot:
 *  - run config (scope/model/delay) survives a tab switch mid-session
 *    (was: Campaign kept it in local state and the view unmounts on tab
 *    switch, so it reset to All 76 / delay 5)
 *  - a blank model disables the Run button
 *  - a stubbed single-case run lands in the results table and the
 *    Evidence badge counts the new live event (was: hardcoded "03")
 *  - the Custom endpoint provider row no longer says "Server-side config"
 *  - the .log-info CSS rule exists, so info log lines get the cyan accent
 *  - the model field's placeholder is not a model name (was:
 *    "gemini-3.5-flash-lite", which read as an entered value on an
 *    empty field) and the delay stepper accepts typed input, clamped
 *    to 0–30 (was: static text, buttons only)
 *  - the notifications bell opens a real panel (was: it only set a
 *    status-strip string, so the tap felt dead): empty state says
 *    "No new system alerts.", real alerts come from live run outcomes
 *    and cases-load failures only, and the panel dismisses via its
 *    close button, Escape, or a tap outside. The bell stays visible
 *    on phones (was: hidden under 560px, so the panel was unreachable
 *    there) with a touch-sized target.
 *  - the notifications panel paints above the hero (was: the topbar's
 *    backdrop-filter trapped the panel below the hero orb, whose
 *    transform-animated rings covered its text, and the panel
 *    background was semi-transparent): the topbar is now a positioned
 *    positive stacking context and the panel background is opaque.
 *  - mobile layout rules (360–430px): the topbar hides its decorative
 *    avatar and the breadcrumb truncates instead of wrapping,
 *    the status strip and notice boxes wrap, the results table has a
 *    min-width so it scrolls inside its own container, small phones
 *    stack provider cards and shrink the hero headline, and the
 *    hamburger / delay buttons / key toggles have touch-sized targets.
 *    jsdom cannot measure real layout, so these pin the CSS rules the
 *    audit found missing — a real-browser check still verifies the
 *    rendered result.
 *  - interactivity audit: every tab, card, and clickable is exercised —
 *    module cards navigate (were hover-only divs), the operator row
 *    opens Configuration (was a static row with a chevron), hamburger
 *    + scrim, bell, GitHub link, provider select/deselect, inline
 *    Configuration / runner links, key show/hide + clear + clear-all,
 *    Stop during a multi-case run, Download report (blob stubbed),
 *    Evidence COPY JSON (clipboard stubbed).
 *
 * Renders the real App in jsdom with fetch stubbed (cases.json from disk,
 * Gemini generateContent canned). Requires jsdom (devDependency) and
 * esbuild (via vite). Exits non-zero on any failure.
 */
"use strict";

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const REACT = require(path.join(ROOT, "node_modules", "react"));
const { createRoot } = require(path.join(ROOT, "node_modules", "react-dom", "client"));
const { act } = require(path.join(ROOT, "node_modules", "react-dom", "test-utils"));
const { JSDOM } = require(path.join(ROOT, "node_modules", "jsdom"));

let passed = 0;
let failed = 0;
function check(name, cond, extra) {
  if (cond) {
    passed++;
    console.log(`PASS ${name}`);
  } else {
    failed++;
    console.log(`FAIL ${name}${extra ? ` — ${extra}` : ""}`);
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const cases = JSON.parse(fs.readFileSync(path.join(ROOT, "public", "cases.json"), "utf8"));

  // Bundle App.tsx (esbuild via vite's dependency) to a temp dir inside
  // the dashboard tree, so the bundle's external react/react-dom resolve
  // from the dashboard's own node_modules (one React copy, not two).
  const tmp = path.join(ROOT, ".tmp-dom-test");
  fs.mkdirSync(tmp, { recursive: true });
  const bundle = path.join(tmp, "app.cjs");
  execFileSync(
    path.join(ROOT, "node_modules", ".bin", "esbuild"),
    [path.join(ROOT, "src", "App.tsx"), "--bundle", "--platform=node", "--format=cjs",
     `--outfile=${bundle}`, "--external:react", "--external:react-dom"],
    { stdio: "pipe" },
  );

  const dom = new JSDOM(`<!doctype html><html><body><div id="root"></div></body></html>`, {
    url: "https://openmind-jailbreak-lab.vercel.app/",
    pretendToBeVisual: true,
  });
  global.window = dom.window;
  global.document = dom.window.document;
  Object.defineProperty(global, "navigator", { value: dom.window.navigator, configurable: true });
  global.HTMLElement = dom.window.HTMLElement;
  global.Node = dom.window.Node;
  global.getComputedStyle = dom.window.getComputedStyle;
  global.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  // jsdom has no scrollIntoView; the Campaign view calls it when a run
  // starts to bring the progress window on screen. Stub it (no-op).
  dom.window.HTMLElement.prototype.scrollIntoView = function () {};
  global.IS_REACT_ACT_ENVIRONMENT = true;

  // Stub fetch: cases.json from disk; Gemini returns a canned response.
  global.fetch = async (url) => {
    if (String(url).includes("cases.json")) {
      return { ok: true, status: 200, headers: { get: () => null }, json: async () => cases };
    }
    if (String(url).includes("generateContent")) {
      const body = {
        candidates: [{
          finishReason: "STOP",
          content: { parts: [{ text: `Fixture mentions ${cases.find(c => c.case_id === "GL-001").canary}.` }] },
          safetyRatings: [],
        }],
      };
      return {
        ok: true, status: 200, headers: { get: () => null },
        json: async () => body, text: async () => JSON.stringify(body),
      };
    }
    throw new Error("unexpected fetch: " + url);
  };

  const App = require(bundle).default;
  const root = createRoot(document.getElementById("root"));
  await act(async () => {
    root.render(REACT.createElement(App));
    await sleep(100);
  });

  const byText = (text, tag = "button") =>
    [...document.querySelectorAll(tag)].find((el) => el.textContent.trim().startsWith(text));
  // Text inputs: drive them with React's Simulate.change. The native
  // setter + 'input' event does NOT trigger React onChange in jsdom
  // (the DOM value changes but React state never updates — verified in
  // a debug run); Simulate is the canonical way to drive controlled
  // inputs in tests. Selects use Simulate too (see setSelect).
  const { Simulate } = require(path.join(ROOT, "node_modules", "react-dom", "test-utils"));
  const setInput = (el, value) => {
    Simulate.change(el, { target: { value } });
  };
  // Selects: drive them with React's Simulate.change too. The native
  // setter + 'change' event is racy in this harness — twice, a select
  // change on a freshly remounted Campaign view silently failed to
  // reach React state (the stop test ran a single case instead of all
  // 76), while the same call worked everywhere else. Simulate invokes
  // the React handler directly, like setInput above.
  const setSelect = (el, value) => {
    Simulate.change(el, { target: { value } });
  };

  // --- Interactivity audit: Overview cards, bell, hamburger, user row.
  // (The three module cards used to be hover-only divs with no handler,
  // and the operator row was a static row with a chevron and no handler.)
  const moduleCard = (title) =>
    [...document.querySelectorAll(".module-card")].find((c) => c.textContent.includes(title));
  await act(async () => { moduleCard("Guardrail evaluation").click(); await sleep(30); });
  check("module card Guardrail evaluation opens the runner", Boolean(document.getElementById("run-scope")));
  await act(async () => { byText("Overview").click(); await sleep(30); });
  await act(async () => { byText("Configure evaluation").click(); await sleep(30); });
  check("Configure evaluation opens the runner", Boolean(document.getElementById("run-scope")));
  await act(async () => { byText("Overview").click(); await sleep(30); });
  await act(async () => { byText("VIEW EVIDENCE LOG").click(); await sleep(30); });
  check("View evidence log opens Evidence", Boolean(document.querySelector(".evidence-panel")));
  await act(async () => { byText("Overview").click(); await sleep(30); });
  await act(async () => { moduleCard("Mutation & replay").click(); await sleep(30); });
  check("module card Mutation & replay opens Documentation", Boolean(document.querySelector(".doc-panel")));
  await act(async () => { byText("Overview").click(); await sleep(30); });
  await act(async () => { moduleCard("Evidence & provenance").click(); await sleep(30); });
  check("module card Evidence & provenance opens Evidence", Boolean(document.querySelector(".evidence-panel")));
  await act(async () => { byText("Overview").click(); await sleep(30); });
  await act(async () => { document.querySelector('[aria-label="Notifications"]').click(); await sleep(30); });
  check("bell sets the notice", document.body.textContent.includes("No new system alerts."));
  // --- Notifications panel: the bell used to only set a status-strip
  // string, so the tap felt dead — no panel, no toast, no feedback.
  // It must open a real panel (empty state when there is nothing to
  // report), and the panel must dismiss three ways.
  check("bell opens the notifications panel", Boolean(document.querySelector(".notif-panel")));
  check("panel is labelled as a dialog",
    document.querySelector(".notif-panel")?.getAttribute("role") === "dialog");
  check("panel shows the no-alerts empty state",
    document.querySelector(".notif-panel")?.textContent.includes("No new system alerts."));
  check("bell reports its expanded state",
    document.querySelector('[aria-label="Notifications"]')?.getAttribute("aria-expanded") === "true");
  await act(async () => { document.querySelector('[aria-label="Close notifications"]').click(); await sleep(30); });
  check("close button dismisses the panel", !document.querySelector(".notif-panel"));
  await act(async () => { document.querySelector('[aria-label="Notifications"]').click(); await sleep(30); });
  await act(async () => {
    document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await sleep(30);
  });
  check("Escape dismisses the panel", !document.querySelector(".notif-panel"));
  await act(async () => { document.querySelector('[aria-label="Notifications"]').click(); await sleep(30); });
  await act(async () => {
    document.body.dispatchEvent(new dom.window.MouseEvent("mousedown", { bubbles: true }));
    await sleep(30);
  });
  check("tap outside dismisses the panel", !document.querySelector(".notif-panel"));
  check("GitHub link points at the repo",
    document.querySelector(".github-link")?.getAttribute("href") === "https://github.com/tjcrims0nx/OpenMind-Jailbreak-Lab");
  await act(async () => { document.querySelector(".mobile-menu").click(); await sleep(30); });
  check("hamburger opens the sidebar",
    document.querySelector(".sidebar")?.classList.contains("sidebar-open") && Boolean(document.querySelector(".scrim")));
  await act(async () => { document.querySelector(".scrim").click(); await sleep(30); });
  check("scrim closes the sidebar", !document.querySelector(".sidebar")?.classList.contains("sidebar-open"));
  await act(async () => { document.querySelector(".user-row").click(); await sleep(30); });
  check("operator row opens Configuration", Boolean(document.querySelector(".key-panel")));

  // --- Tab 1: Campaign runner is reachable and cases loaded.
  await act(async () => { byText("Campaign runner").click(); await sleep(30); });
  check("runner shows scope select", Boolean(document.getElementById("run-scope")));

  // --- Fix 1: config survives a tab switch.
  await act(async () => {
    setSelect(document.getElementById("run-scope"), "source");
    setInput(document.getElementById("run-model"), "gemini-2.0-flash");
    await sleep(20);
  });
  const inc = document.querySelector('[aria-label="Increase delay"]');
  for (let i = 0; i < 5; i++) await act(async () => { inc.click(); await sleep(10); });
  check("scope set to source before switch", document.getElementById("run-scope").value === "source");
  check("delay set to 10 before switch", document.querySelector(".number-control input")?.value === "10",
    `got ${document.querySelector(".number-control input")?.value}`);
  check("model set before switch", document.getElementById("run-model").value === "gemini-2.0-flash");
  await act(async () => { byText("Evidence").click(); await sleep(30); });
  await act(async () => { byText("Campaign runner").click(); await sleep(30); });
  check("scope survives tab switch", document.getElementById("run-scope").value === "source",
    `got ${document.getElementById("run-scope")?.value}`);
  check("delay survives tab switch", document.querySelector(".number-control input")?.value === "10",
    `got ${document.querySelector(".number-control input")?.value}`);
  check("model survives tab switch", document.getElementById("run-model").value === "gemini-2.0-flash",
    `got ${document.getElementById("run-model")?.value}`);

  // --- Fix 6: model placeholder must not read as a model name.
  check("model placeholder is not a model name",
    document.getElementById("run-model").getAttribute("placeholder") === "model name",
    `got ${document.getElementById("run-model")?.getAttribute("placeholder")}`);

  // --- Fix 7: delay accepts typed input (was: static text, buttons only).
  const delayInput = document.querySelector(".number-control input");
  check("delay has a typable input", Boolean(delayInput));
  if (delayInput) {
    await act(async () => { setInput(delayInput, "12"); await sleep(20); });
    check("typed delay updates the field", delayInput.value === "12", `got ${delayInput.value}`);
    const delayRow = [...document.querySelectorAll(".summary-row")]
      .find((r) => r.textContent.startsWith("Delay"));
    check("run summary reflects typed delay", Boolean(delayRow?.textContent.includes("12s")),
      `got ${delayRow?.textContent}`);
    await act(async () => { setInput(delayInput, "99"); await sleep(20); });
    check("typed delay clamps to 30", delayInput.value === "30", `got ${delayInput.value}`);
    await act(async () => { setInput(delayInput, ""); await sleep(20); });
    check("clearing delay leaves the field empty until blur", delayInput.value === "");
    await act(async () => { Simulate.blur(delayInput); await sleep(20); });
    check("blur restores the committed delay", delayInput.value === "30", `got ${delayInput.value}`);
    await act(async () => { setInput(delayInput, "10"); await sleep(20); });
    check("delay restored to 10", delayInput.value === "10", `got ${delayInput.value}`);
  }

  // --- Fix 5: blank model disables Run.
  await act(async () => {
    setInput(document.getElementById("run-model"), "");
    await sleep(20);
  });
  const runBtn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Run campaign"));
  check("blank model disables Run", runBtn.disabled === true);
  check("blank model shows hint", document.body.textContent.includes("Enter a model name to run"));
  await act(async () => {
    setInput(document.getElementById("run-model"), "gemini-3.5-flash-lite");
    await sleep(20);
  });

  // --- Fix 2: stubbed single-case run + Evidence badge counts the live event.
  await act(async () => { byText("Configuration").click(); await sleep(30); });
  const keyInput = document.querySelector('input[aria-label="Google Gemini API key"]');
  check("Configuration has Gemini key input", Boolean(keyInput));
  await act(async () => { setInput(keyInput, "test-key-not-real"); await sleep(20); });
  await act(async () => { byText("Campaign runner").click(); await sleep(30); });
  await act(async () => {
    setSelect(document.getElementById("run-scope"), "single");
    await sleep(20);
  });
  await act(async () => {
    const single = document.getElementById("run-single");
    setSelect(single, "GL-001");
    await sleep(20);
  });
  const runBtn2 = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Run campaign"));
  check("Run enabled with key + model", runBtn2.disabled === false);
  await act(async () => { runBtn2.click(); await sleep(300); });
  // Wait for the run to finish (single case, no delay).
  for (let i = 0; i < 40 && document.body.textContent.includes("Running…"); i++) {
    await act(async () => { await sleep(100); });
  }
  check("run finished", !document.body.textContent.includes("Running…"));
  check("results table shows GL-001", document.body.textContent.includes("GL-001"));
  check("log shows GL-001 line", [...document.querySelectorAll(".log-line")].some((l) => l.textContent.includes("GL-001")));
  const review = () => document.querySelector('.review-select[aria-label="Review GL-001"]');
  await act(async () => { setSelect(review(), "needs_review"); });
  await act(async () => { byText("Evidence").click(); });
  await act(async () => { byText("Campaign runner").click(); });
  check("review survives navigation", review()?.value === "needs_review");
  const badge = document.querySelector(".nav-count")?.textContent;
  check("Evidence badge counts live event (04)", badge === "04", `got ${badge}`);

  // --- Fix 3: Custom endpoint label.
  await act(async () => { byText("Providers").click(); await sleep(30); });
  check("Custom endpoint no longer says Server-side config",
    !document.body.textContent.includes("Server-side config"));
  check("Custom endpoint says Not applicable", document.body.textContent.includes("Not applicable"));

  // --- Providers: target toggle + inline Configuration link.
  const providerCard = (name) =>
    [...document.querySelectorAll(".provider-card")].find((c) => c.textContent.includes(name));
  const anthropicBtn = () => providerCard("Anthropic")?.querySelector(".select-provider");
  check("Anthropic starts unselected", anthropicBtn()?.textContent.includes("Add target"));
  await act(async () => { anthropicBtn().click(); await sleep(20); });
  check("provider toggle selects a target", anthropicBtn()?.textContent.includes("Selected"));
  await act(async () => { anthropicBtn().click(); await sleep(20); });
  check("provider toggle deselects again", anthropicBtn()?.textContent.includes("Add target"));
  const inlineConfig = [...document.querySelectorAll("button.inline-action")]
    .find((b) => b.textContent.trim() === "Configuration");
  await act(async () => { inlineConfig.click(); await sleep(30); });
  check("Providers notice link opens Configuration", Boolean(document.querySelector(".key-panel")));

  // --- Documentation: inline navigation buttons.
  await act(async () => { byText("Documentation").click(); await sleep(30); });
  const docConfig = [...document.querySelectorAll("button.inline-action")]
    .find((b) => b.textContent.trim() === "Configuration");
  await act(async () => { docConfig.click(); await sleep(30); });
  check("Documentation link opens Configuration", Boolean(document.querySelector(".key-panel")));
  await act(async () => { byText("Documentation").click(); await sleep(30); });
  const docRunner = [...document.querySelectorAll("button.inline-action")]
    .find((b) => b.textContent.trim() === "Campaign runner");
  await act(async () => { docRunner.click(); await sleep(30); });
  check("Documentation link opens the runner", Boolean(document.getElementById("run-scope")));

  // --- Configuration: show/hide, clear one key, clear all.
  await act(async () => { byText("Configuration").click(); await sleep(30); });
  const geminiInput = () => document.querySelector('input[aria-label="Google Gemini API key"]');
  check("Gemini key still set", geminiInput()?.value === "test-key-not-real");
  await act(async () => { document.querySelector('[aria-label="Show Google Gemini key"]').click(); await sleep(20); });
  check("show key reveals the value", geminiInput()?.type === "text");
  await act(async () => { document.querySelector('[aria-label="Hide Google Gemini key"]').click(); await sleep(20); });
  check("hide key masks the value again", geminiInput()?.type === "password");
  await act(async () => { document.querySelector('[aria-label="Clear Google Gemini key"]').click(); await sleep(20); });
  check("clear key empties the field", geminiInput()?.value === "");
  await act(async () => { setInput(geminiInput(), "test-key-not-real"); await sleep(20); });
  const openaiInput = () => document.querySelector('input[aria-label="OpenAI API key"]');
  await act(async () => { setInput(openaiInput(), "test-openai-key"); await sleep(20); });
  await act(async () => { byText("CLEAR ALL KEYS").click(); await sleep(20); });
  check("clear all empties the Gemini key", geminiInput()?.value === "");
  check("clear all empties the OpenAI key", openaiInput()?.value === "");
  await act(async () => { setInput(geminiInput(), "test-key-not-real"); await sleep(20); });

  // --- Fix 4: .log-info CSS rule present.
  const css = fs.readFileSync(path.join(ROOT, "src", "styles.css"), "utf8");
  check(".log-info rule exists in styles.css", css.includes(".log-info{border-left-color:var(--cyan)}"));

  // --- Mobile layout: pin the rules the phone-width audit found missing.
  // jsdom cannot measure real layout (no viewport, no media-query
  // evaluation), so these check the CSS text itself, like the .log-info
  // check above. A real-browser check verifies the rendered result.
  check("mobile hides topbar avatar but keeps the bell with a touch-sized target (was: bell hidden, so the panel was unreachable on phones)",
    css.includes(".top-actions .top-avatar{display:none}")
    && !css.includes(".top-actions .icon-btn,.top-actions .top-avatar{display:none}")
    && css.includes(".top-actions .icon-btn{padding:12px}"));
  check("mobile breadcrumb truncates with ellipsis",
    css.includes(".breadcrumb{font-size:8px;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"));
  check("mobile status strip wraps",
    css.includes(".status-left{flex-wrap:wrap}"));
  check("mobile status right drops its column indent",
    css.includes(".status-right{margin-left:0}"));
  check("mobile notice wraps with its action on its own line",
    css.includes(".notice{flex-wrap:wrap}") && css.includes(".notice .text-action{margin-left:auto}"));
  check("results table has a min-width so it scrolls inside its container",
    css.includes(".results-table{width:100%;min-width:520px;"));
  check("results cells break long unbroken tokens",
    css.includes(".results-table td{padding:8px 10px;border-bottom:1px solid #ffffff0b;vertical-align:top;overflow-wrap:anywhere}"));
  check("small phones shrink the hero headline and stack provider cards",
    css.includes("@media(max-width:400px){h1{font-size:31px;letter-spacing:-1.6px}.providers-grid{grid-template-columns:1fr}}"));
  check("mobile hamburger has a touch-sized target",
    css.includes(".mobile-menu{padding:12px}"));
  check("mobile delay buttons are touch-sized",
    css.includes(".number-control button{width:34px}"));
  check("mobile key toggles are touch-sized",
    css.includes(".key-toggle{padding:10px}"));
  check("bell + avatar still in the DOM (avatar hidden by CSS, bell shown)",
    Boolean(document.querySelector(".top-actions .icon-btn"))
    && Boolean(document.querySelector(".top-actions .top-avatar")));
  check("notifications panel is anchored under the bell and fits phone widths",
    css.includes(".notif-panel{position:absolute;top:calc(100% + 10px);right:0;width:340px;max-width:calc(100vw - 24px);"));
  // --- Notifications panel layering: the panel must paint above the hero.
  // The topbar's backdrop-filter creates a stacking context, so the
  // panel's own z-index could not escape it — the hero orb's
  // transform-animated rings (later in tree order) painted over the
  // panel's text. The topbar is now a positioned positive stacking
  // context, and the panel background is fully opaque (was #101522f2,
  // so the hero showed through even where the panel was on top).
  check("topbar is a positioned positive stacking context so the notifications panel paints above the hero",
    css.includes(".topbar{position:relative;z-index:50;"));
  check("notifications panel background is fully opaque",
    css.includes("background:#101522;") && !css.includes("background:#101522f2"));
  check("notifications badge rule exists",
    css.includes(".notif-badge{position:absolute;"));
  // The table only renders while the Campaign tab is active — the
  // Providers check above unmounted it, so switch back first. Results
  // persist in App state, so the table re-renders.
  await act(async () => { byText("Campaign runner").click(); await sleep(30); });
  check("results table sits inside its scroll container",
    Boolean(document.querySelector(".results-wrap .results-table")));

  // --- Stop: a multi-case run can be aborted mid-wait (the earlier
  // single-case run finished too fast to show the Stop button).
  await act(async () => { setSelect(document.getElementById("run-scope"), "all"); await sleep(20); });
  const delayInput2 = document.querySelector(".number-control input");
  await act(async () => { setInput(delayInput2, "30"); await sleep(20); });
  const runBtn3 = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Run campaign"));
  check("Run enabled for the stop test", runBtn3.disabled === false);
  await act(async () => { runBtn3.click(); await sleep(300); });
  check("new campaign starts with a fresh review", review()?.value === "");
  const stopBtn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Stop campaign"));
  check("Stop button appears while running", Boolean(stopBtn));
  if (stopBtn) {
    await act(async () => { stopBtn.click(); await sleep(300); });
  }
  check("Stop ends the run with a stopped message",
    document.body.textContent.includes("Stopped by you"));
  check("Stop keeps the completed case",
    [...document.querySelectorAll(".log-line")].some((l) => l.textContent.includes("GL-001")));

  // --- Notifications panel with a real alert: the stopped run recorded
  // a live warn event, so the panel must list it (not the empty state)
  // and the bell must show the count.
  check("bell shows an alert count badge",
    document.querySelector(".notif-badge")?.textContent === "1",
    `got ${document.querySelector(".notif-badge")?.textContent}`);
  await act(async () => { document.querySelector(".notif-btn").click(); await sleep(30); });
  check("panel lists the stopped-run alert",
    document.querySelector(".notif-panel")?.textContent.includes("Live campaign stopped"));
  await act(async () => { document.querySelector('[aria-label="Close notifications"]').click(); await sleep(30); });
  check("panel closes after showing an alert", !document.querySelector(".notif-panel"));

  // --- Download report: the button builds a real JSON report blob.
  // Stub the browser-only parts (object URL + anchor click) to prove
  // the handler wires them correctly.
  let capturedBlob = null;
  let capturedDownload = null;
  const origCreateObjectURL = global.URL.createObjectURL;
  const origAnchorClick = dom.window.HTMLAnchorElement.prototype.click;
  global.URL.createObjectURL = (blob) => { capturedBlob = blob; return "blob:test-report"; };
  dom.window.HTMLAnchorElement.prototype.click = function () {
    capturedDownload = this.getAttribute("download");
  };
  const dlBtn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("DOWNLOAD JSON"));
  check("download button appears after a run", Boolean(dlBtn));
  if (dlBtn) {
    await act(async () => { dlBtn.click(); await sleep(20); });
  }
  check("download creates a JSON blob",
    Boolean(capturedBlob) && capturedBlob.type === "application/json",
    capturedBlob ? `type ${capturedBlob.type}` : "no blob captured");
  const reportText = capturedBlob ? await capturedBlob.text() : "";
  check("downloaded report is the guardrail report",
    reportText.includes('"tool": "guardrail-lab"') && reportText.includes("GL-001"));
  check("download filename ends in .json",
    typeof capturedDownload === "string" && capturedDownload.endsWith(".json"),
    `got ${capturedDownload}`);
  global.URL.createObjectURL = origCreateObjectURL;
  dom.window.HTMLAnchorElement.prototype.click = origAnchorClick;

  // --- Evidence: COPY JSON copies the ledger (clipboard stubbed, since
  // jsdom has no clipboard — the handler's no-clipboard fallback is a
  // separate branch, not covered here).
  let copiedText = null;
  Object.defineProperty(dom.window.navigator, "clipboard", {
    value: { writeText: async (t) => { copiedText = t; } },
    configurable: true,
  });
  await act(async () => { byText("Evidence").click(); await sleep(30); });
  const copyBtn = [...document.querySelectorAll("button")].find((b) => b.textContent.includes("COPY JSON"));
  check("Evidence has a copy button", Boolean(copyBtn));
  if (copyBtn) {
    await act(async () => { copyBtn.click(); await sleep(50); });
  }
  let copiedOk = false;
  try {
    const parsed = JSON.parse(copiedText || "null");
    copiedOk = Array.isArray(parsed) && parsed.length >= 4
      && parsed.some((e) => e.title && e.title.includes("Live campaign"));
  } catch { copiedOk = false; }
  check("copy JSON copies the event ledger", copiedOk,
    copiedText ? `got ${String(copiedText).slice(0, 80)}` : "nothing copied");
  check("copy reports success in the notice",
    document.body.textContent.includes("Evidence JSON copied to clipboard."));

  // --- Static: no key storage APIs actually used in src. (The words
  // appear in comments and UI copy — "never written to localStorage" —
  // so match property access, not bare mentions.)
  const src = fs.readFileSync(path.join(ROOT, "src", "App.tsx"), "utf8")
    + fs.readFileSync(path.join(ROOT, "src", "guardrail.ts"), "utf8");
  check("no localStorage/sessionStorage use in src",
    !/\blocalStorage\s*\.|\bsessionStorage\s*\.|window\.localStorage|window\.sessionStorage/.test(src));

  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}

main().catch((e) => { console.error("TEST ERROR:", e); process.exit(2); });
