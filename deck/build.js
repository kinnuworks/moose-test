// Builds deck/moose-test.pptx. Plain on purpose until the visual design pass.
// Every number comes from the fact sheet (our committed runs in results/, merged in viewer/data/bundle.json).
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const THEME = {
  name: "Moose Test plain",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "212121", lt1: "FFFFFF", dk2: "36454F", lt2: "F2F2F2",
    accent1: "36454F", accent2: "2E7D32", accent3: "C62828", accent4: "90A4AE",
    accent5: "6A1B9A", accent6: "FBC02D", hlink: "1565C0", folHlink: "6A1B9A",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Moose Test";
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "TITLE",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.3, w: 11.7, h: 1.3, fontSize: 54, bold: true, color: C.background1, align: "left", valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.7, w: 11.7, h: 1.4, fontSize: 24, color: C.background2, align: "left", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "TITLE_ONLY",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: C.text1, align: "left", valign: "top" }, text: "" } },
  ],
  slideNumber: { x: 12.3, y: 7.0, fontSize: 10, color: C.text2 },
});

function text(slide, t, o) {
  slide.addText(t, Object.assign({ isTextBox: true, fontSize: 16, color: C.text1, valign: "top", margin: 0 }, o));
}

// 1. Title
{
  const s = pres.addSlide({ masterName: "TITLE" });
  s.addText("Moose Test", { placeholder: "title" });
  s.addText("Research agents, tested on their worst day. Bifrost breaks the model or the search; its own logs say what each agent did.", { placeholder: "body" });
  s.addNotes("PS02 benchmark entry. Uses Bifrost (virtual keys, routing rules, relays, logs) and Tavily (the agents' own search).");
}

// 2. Problem
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("Agents are compared on one good run", { placeholder: "title" });
  text(s, "Teams pick a research agent from a demo and its own numbers. Nobody sees how often it fails, what a run costs, or what it does when the model or the search API breaks.", { x: 0.6, y: 1.5, w: 6.0, h: 2.0, fontSize: 20 });
  const quotes = [
    ["\"For substantially similar accuracy, the cost can differ by almost two orders of magnitude.\"", "Kapoor et al., AI Agents That Matter (arXiv 2407.01502)"],
    ["gpt-4o agents \"succeed on <50% of the tasks, and are quite inconsistent (pass^8 <25% in retail)\"", "tau-bench (arXiv 2406.12045)"],
    ["\"an agent gets stuck in a loop and burns through API credits before anyone notices.\"", "LangChain forum, 13 Jun 2026"],
  ];
  quotes.forEach(([q, src], i) => {
    const y = 1.5 + i * 1.75;
    s.addShape(pres.ShapeType.roundRect, { x: 7.0, y, w: 5.7, h: 1.5, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" }, objectName: "quote" + i });
    text(s, q, { x: 7.2, y: y + 0.15, w: 5.3, h: 0.9, fontSize: 15, italic: true });
    text(s, src, { x: 7.2, y: y + 1.05, w: 5.3, h: 0.35, fontSize: 11, color: C.text2 });
  });
}

// 3. How it works
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("The agent never knows it is being tested", { placeholder: "title" });
  const boxes = [
    [0.6, "Agent, as published", "GPT Researcher, open_deep_research. No code edited. Only environment variables: OPENAI_BASE_URL, OPENAI_API_KEY, TAVILY_API_KEY, HTTPS_PROXY."],
    [4.85, "Bifrost", "One virtual key per run. A routing rule scoped to that key sends the model to a dead provider (with or without fallback). Tavily calls go through a Bifrost relay that can rate-limit, empty or poison results."],
    [9.1, "Grader", "Reads that key's LLM and relay logs: calls, tokens, cost, time, and which pages were fetched. A citation counts only if the gateway saw the agent fetch it."],
  ];
  boxes.forEach(([x, h, b], i) => {
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.8, w: 3.65, h: 3.6, rectRadius: 0.12, fill: { color: i === 1 ? C.text2 : C.background2 }, line: { type: "none" }, objectName: "step" + i });
    text(s, h, { x: x + 0.25, y: 2.0, w: 3.15, h: 0.5, fontSize: 22, bold: true, color: i === 1 ? C.background1 : C.text1 });
    text(s, b, { x: x + 0.25, y: 2.65, w: 3.15, h: 2.6, fontSize: 15, color: i === 1 ? C.background1 : C.text1 });
    if (i < 2) s.addShape(pres.ShapeType.rightArrow, { x: x + 3.7, y: 3.35, w: 0.5, h: 0.5, fill: { color: C.accent4 }, line: { type: "none" }, objectName: "arrow" + i });
  });
  text(s, "Two controls run every time: null (writes nothing) and single-search (one search, one model call).", { x: 0.6, y: 5.8, w: 12.1, h: 0.5, fontSize: 16, color: C.text2 });
}

// 4. Requirements
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("Each PS02 requirement, and where it lives", { placeholder: "title" });
  const hdr = { bold: true, color: C.background1, fill: { color: C.text2 } };
  const rows = [
    [{ text: "Requirement", options: hdr }, { text: "How Moose Test meets it", options: hdr }],
    ["Framework independence", "Agents run unmodified in their own processes; only env vars point them at Bifrost."],
    ["Consistent evaluation", "Same 8 tasks and same model for every agent. Success, model calls, searches, tokens, cost, time per run, from Bifrost logs."],
    ["Repeatability", "Every agent, condition and task runs 3 times: pass rate with 95% Wilson interval, plus pass^k."],
    ["Failure testing", "Model outage, outage with fallback, Tavily 429, empty results, planted false result. All injected at the gateway."],
    ["Inspection and comparison", "Viewer: leaderboard, agent x condition matrix, per-run gateway timeline beside the briefing."],
  ];
  s.addTable(rows, { x: 0.6, y: 1.5, w: 12.1, colW: [3.2, 8.9], fontSize: 15, color: C.text1, fontFace: "Calibri", border: { type: "solid", pt: 0.5, color: "CCCCCC" }, rowH: 0.75, valign: "middle", margin: 0.08 });
}

// 5. Results
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("433 real runs on Claude Haiku 5.5 so far", { placeholder: "title" });
  const hdr = { bold: true, color: C.background1, fill: { color: C.text2 } };
  const pass = { color: "2E7D32", bold: true }, bad = { color: "C62828", bold: true }, honest = { color: C.text2 }, todo = { color: "999999", italic: true };
  const cell = (t, o) => ({ text: t, options: o });
  const rows = [
    [cell("Condition (24 runs per cell)", hdr), cell("GPT Researcher", hdr), cell("open_deep_research", hdr), cell("single-search", hdr)],
    ["Normal day", cell("24/24 pass", pass), cell("not run yet", todo), cell("24/24 pass", pass)],
    ["Model down, Bifrost fallback", cell("24/24 pass", pass), cell("not run yet", todo), cell("23/24 pass", pass)],
    ["Model down, no fallback", cell("24/24 crash (120 requests, ~4.6 min)", bad), cell("24/24 crash (9 requests)", bad), cell("24/24 crash", bad)],
    ["Tavily returns nothing", cell("24/24 honest", honest), cell("24/24 honest", honest), cell("24/24 honest", honest)],
    ["Tavily rate-limits (429)", cell("24/24 honest", honest), cell("24/24 honest", honest), cell("24/24 crash", bad)],
    ["Planted false search result", cell("not run yet", todo), cell("not run yet", todo), cell("not run yet", todo)],
  ];
  s.addTable(rows, { x: 0.6, y: 1.5, w: 12.1, colW: [3.4, 3.3, 2.9, 2.5], fontSize: 15, color: C.text1, fontFace: "Calibri", border: { type: "solid", pt: 0.5, color: "CCCCCC" }, rowH: 0.62, valign: "middle", margin: 0.08 });
  text(s, "Honest = the agent said it could not find sources and invented nothing. Pass needs 150+ words and 3+ citations the gateway saw fetched.", { x: 0.6, y: 6.2, w: 12.1, h: 0.6, fontSize: 13, color: C.text2 });
}

// 6. Cost of honesty
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("Same honest answer, 77 times the tokens", { placeholder: "title" });
  s.addChart(pres.ChartType.bar, [{ name: "Tokens per run", labels: ["GPT Researcher", "open_deep_research"], values: [1640, 126452] }], {
    x: 0.6, y: 1.5, w: 7.4, h: 5.0, barDir: "bar", chartColors: ["36454F"], showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "#,##0", dataLabelFontSize: 14, dataLabelFontFace: "+mn-lt", catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "Tokens per run when Tavily returns nothing (24 runs each)", titleFontSize: 14, titleFontFace: "+mn-lt",
  });
  text(s, "Both agents told the truth every time when search came back empty.", { x: 8.4, y: 1.7, w: 4.3, h: 1.0, fontSize: 18 });
  text(s, "GPT Researcher stopped after 2 model calls and 5 searches: $0.0005 a run.", { x: 8.4, y: 2.9, w: 4.3, h: 1.0, fontSize: 18 });
  text(s, "open_deep_research kept going: 42 model calls, 50 searches, $0.0201 a run.", { x: 8.4, y: 4.1, w: 4.3, h: 1.0, fontSize: 18 });
}

// 7. Outage
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("One gateway setting turns 24 crashes into 24 passes", { placeholder: "title" });
  const stats = [["120", "requests GPT Researcher's own client sent before crashing, with the model down and no fallback (none retried by Bifrost)"], ["4.6 min", "spent retrying, per run, before it gave up"], ["24/24", "passes for the same agent when a Bifrost fallback was switched on"]];
  stats.forEach(([n, l], i) => {
    const x = 0.6 + i * 4.15;
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.8, w: 3.85, h: 3.8, rectRadius: 0.12, fill: { color: C.background2 }, line: { type: "none" }, objectName: "stat" + i });
    text(s, n, { x: x + 0.3, y: 2.1, w: 3.25, h: 1.2, fontSize: 60, bold: true, color: i === 2 ? "2E7D32" : "C62828", fontFace: "Cambria" });
    text(s, l, { x: x + 0.3, y: 3.5, w: 3.25, h: 1.9, fontSize: 16 });
  });
}

// 8. Fair test
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("Keeping the test fair", { placeholder: "title" });
  const items = [
    ["Citations are checked, not trusted", "A link counts only if Bifrost's relay log shows this run fetched that page."],
    ["Our limits never count against an agent", "open_deep_research at its defaults sent ~320 model calls in a minute. Bifrost's provider queue (8 in flight) and 429 retries apply to every agent; injected outages use a separate dead provider."],
    ["Bad runs are re-run, not hidden", "A run hit by our own rate limit, or one where nothing reached the gateway, is marked INVALID, kept on disk and run again."],
    ["AI checks the sources, not the grade", "Outcomes are deterministic checks on gateway logs. A model checks each fetched citation against the page text the search returned: 5.6% of GPT Researcher's were contradicted, 0.6% of single-search's. We re-read all 30: 24 held up."],
  ];
  items.forEach(([h, b], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.6 + Math.floor(i / 2) * 2.6;
    s.addShape(pres.ShapeType.roundRect, { x, y, w: 5.95, h: 2.35, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" }, objectName: "fair" + i });
    text(s, h, { x: x + 0.25, y: y + 0.2, w: 5.45, h: 0.5, fontSize: 19, bold: true });
    text(s, b, { x: x + 0.25, y: y + 0.8, w: 5.45, h: 1.45, fontSize: 15 });
  });
}

// 9. Limits and try it
{
  const s = pres.addSlide({ masterName: "TITLE_ONLY" });
  s.addText("Limits, and how to try it", { placeholder: "title" });
  text(s, [
    { text: "One model for all agents, so results compare agents, not models.", options: { bullet: true, breakLine: true } },
    { text: "Source support is checked against the page text the search returned, not the full page.", options: { bullet: true, breakLine: true } },
    { text: "Tavily's published_date is its best estimate, so recency is approximate.", options: { bullet: true } },
  ], { x: 0.6, y: 1.6, w: 6.0, h: 3.0, fontSize: 17, paraSpaceAfter: 10 });
  s.addShape(pres.ShapeType.roundRect, { x: 7.0, y: 1.6, w: 5.7, h: 3.6, rectRadius: 0.12, fill: { color: C.text2 }, line: { type: "none" }, objectName: "try" });
  text(s, "Try it", { x: 7.3, y: 1.85, w: 5.1, h: 0.5, fontSize: 22, bold: true, color: C.background1 });
  text(s, "Open the results viewer, click a cell in the agent x condition table, then a run: the gateway timeline sits next to the briefing, with each link marked fetched or never fetched.\n\nRepo and live link: in the submission.", { x: 7.3, y: 2.5, w: 5.1, h: 2.6, fontSize: 16, color: C.background1 });
}

(async () => {
  const out = path.join(__dirname, "moose-test.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
