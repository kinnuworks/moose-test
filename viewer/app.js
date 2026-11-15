const OUTCOMES = ["PASS", "HONEST_FAIL", "WEAK", "SILENT_DEGRADE", "CRASH", "NO_OUTPUT", "INVALID"];
const OUTCOME_TEXT = {
  PASS: "passed", HONEST_FAIL: "failed honestly", WEAK: "too thin",
  SILENT_DEGRADE: "failed silently", CRASH: "crashed", NO_OUTPUT: "wrote nothing", INVALID: "not counted: our own rate limit, re-run",
};
const CONTROLS = new Set(["null", "single-search"]);
let B = null;

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("data-")) e.setAttribute(k, v); else e[k] = v;
  }
  for (const k of kids) e.append(k);
  return e;
};
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
const money = (x) => (x == null ? "–" : "$" + x.toFixed(x < 0.01 ? 4 : 3));

function agentTotals(agent) {
  const cells = B.suite.summary.cells[agent] || {};
  let fn = 0, fsafe = 0, silent = 0, cost = 0, passes = 0, llm = 0, tav = 0, n = 0, tok = 0;
  for (const [cond, c] of Object.entries(cells)) {
    n += c.n; cost += c.cost; tok += (c.tokens_per_run || 0) * c.n; passes += c.pass; llm += c.llm_calls * c.n; tav += c.tavily_calls * c.n;
    silent += c.outcomes.SILENT_DEGRADE || 0;
    if (cond !== "baseline") { fn += c.n; fsafe += c.safe; }
  }
  const base = cells.baseline;
  return {
    normal: base ? base.pass_rate : null, normalCi: base ? base.pass_ci : null,
    passk: base ? base.pass_hat_k : null, safe: fn ? fsafe / fn : null, silent, n,
    costPerPass: passes ? cost / passes : null, costPerRun: n ? cost / n : null, tokens: n ? tok / n : 0,
    llm: n ? llm / n : 0, tav: n ? tav / n : 0,
  };
}

function renderLeaderboard() {
  const rows = B.suite.agents.map((a) => [a, agentTotals(a)]);
  // real agents first, controls last; within each, by normal-day pass rate then behaviour under faults
  rows.sort((x, y) => (CONTROLS.has(x[0]) - CONTROLS.has(y[0])) ||
    (y[1].normal ?? -1) - (x[1].normal ?? -1) || (y[1].safe ?? -1) - (x[1].safe ?? -1));
  const tb = $("#leaderboard tbody");
  tb.replaceChildren();
  for (const [a, t] of rows) {
    const ci = t.normalCi ? ` (${pct(t.normalCi[0])}–${pct(t.normalCi[1])})` : "";
    const notRun = t.normal == null ? "not run yet" : null;
    tb.append(el("tr", { class: CONTROLS.has(a) ? "control" : "" },
      el("td", {}, a + (CONTROLS.has(a) ? " (control)" : "")),
      el("td", {}, notRun || pct(t.normal) + ci), el("td", {}, notRun || pct(t.passk)), el("td", {}, pct(t.safe)),
      el("td", {}, String(t.silent)), el("td", {}, money(t.costPerPass)), el("td", {}, money(t.costPerRun)),
      el("td", {}, Math.round(t.tokens).toLocaleString()),
      el("td", {}, t.llm.toFixed(1)), el("td", {}, t.tav.toFixed(1)), el("td", {}, supportText(a))));
  }
}

function supportText(agent) {
  const cells = (B.suite.support || {})[agent] || {};
  let checked = 0, bad = 0, errored = 0;
  for (const c of Object.values(cells)) { checked += c.checked; bad += c.contradicted; errored += c.errored_runs || 0; }
  const err = errored ? `; ${errored} run${errored > 1 ? "s" : ""} could not be checked` : "";
  return checked ? `${bad} of ${checked} (${(100 * bad / checked).toFixed(1)}%)${err}` : (errored ? `${errored} runs could not be checked` : "–");
}

const VERDICT_TEXT = { supported: "supported", not_in_source: "not in the returned text", contradicted: "contradicted" };

function renderSupport(r) {
  const box = $("#support");
  const s = r.support;
  if (!s) { box.hidden = true; return; }
  box.hidden = false;
  if (s.error) { box.replaceChildren(el("p", { class: "bad" }, "AI source check failed: " + s.error)); return; }
  const c = s.counts;
  const ul = el("ul", { class: "support" });
  for (const it of s.items) {
    ul.append(el("li", { class: "v-" + it.verdict },
      el("b", {}, VERDICT_TEXT[it.verdict] + ": "), it.claim, " ",
      el("span", { class: "hint" }, "(" + it.reason + ")")));
  }
  box.replaceChildren(
    el("h4", {}, `Do the sources back the briefing? ${c.supported} supported, ${c.contradicted} contradicted, ${c.not_in_source} not in the returned text`),
    el("p", { class: "hint" }, `AI-written by ${s.written_by}, comparing each citing line with the page text the search returned through the gateway. It does not change the outcome above.`),
    ul);
}

function renderMatrix() {
  const conds = B.suite.conditions;
  const head = el("tr", {}, el("th", {}, "Agent"));
  for (const c of conds) head.append(el("th", {}, B.suite.condition_labels[c] || c));
  $("#matrix thead").replaceChildren(head);
  const tb = $("#matrix tbody");
  tb.replaceChildren();
  for (const a of B.suite.agents) {
    const tr = el("tr", {}, el("th", {}, a));
    for (const c of conds) {
      const cell = (B.suite.summary.cells[a] || {})[c];
      const td = el("td", { class: "cell", "data-agent": a, "data-cond": c, tabIndex: 0 });
      if (cell) {
        const bar = el("div", { class: "bar" });
        for (const o of OUTCOMES) {
          const k = cell.outcomes[o] || 0;
          if (k) bar.append(el("span", { class: "seg " + o, style: `flex:${k}`, title: `${k} ${OUTCOME_TEXT[o]}` }));
        }
        td.append(bar, el("div", { class: "small" }, `${cell.pass}/${cell.n} passed`));
      } else td.append(el("span", { class: "small" }, "not run yet"));
      td.addEventListener("click", () => openCell(a, c));
      td.addEventListener("keydown", (e) => e.key === "Enter" && openCell(a, c));
      tr.append(td);
    }
    tb.append(tr);
  }
  const lg = $("#legend");
  lg.replaceChildren();
  for (const o of OUTCOMES) lg.append(el("span", { class: "key " + o }), " " + OUTCOME_TEXT[o] + "  ");
}

function openCell(agent, cond) {
  const runs = B.runs.filter((r) => r.agent === agent && r.condition === cond);
  $("#drill").hidden = false;
  $("#drill-title").textContent = `${agent} — ${B.suite.condition_labels[cond] || cond} (${runs.length} runs)`;
  const ul = $("#runs");
  ul.replaceChildren();
  if (!runs.length) ul.append(el("li", { class: "empty" }, "Not run yet: this agent has no runs under this condition in these results."));
  for (const r of runs) {
    const a = el("a", { href: "#" + r.run_id }, `${r.company}, repeat ${r.repeat + 1}: ${OUTCOME_TEXT[r.grade.outcome]}`);
    a.addEventListener("click", (e) => { e.preventDefault(); openRun(r); });
    ul.append(el("li", {}, a));
  }
  $("#drill").scrollIntoView({ behavior: "smooth" });
}

function openRun(r) {
  $("#run").hidden = false;
  $("#run h3").textContent = `${r.agent} · ${B.suite.condition_labels[r.condition] || r.condition} · ${r.company} · repeat ${r.repeat + 1}`;
  const g = r.grade;
  $("#run-facts").textContent =
    `Outcome: ${OUTCOME_TEXT[g.outcome]}. ${r.llm.calls} model calls (${r.llm.errors} failed, ${r.llm.fallbacks} served by fallback), ` +
    `${r.tavily.calls} searches, ${g.cited} cited links (${g.verified} fetched in this run, ${g.unverified} never fetched)` +
    (g.echoed_planted_claim ? ", repeated the planted false claim" : "") +
    `, ${r.wall_s}s, ${money(r.llm.cost)} model cost, exit code ${r.exit_code}.`;
  const dg = $("#diagnosis");
  if (r.diagnosis && r.diagnosis.diagnosis) {
    dg.hidden = false;
    dg.replaceChildren(el("b", {}, "AI-written diagnosis: "), r.diagnosis.diagnosis,
      el("span", { class: "hint" }, ` (${r.diagnosis.written_by || "no model"}, from this run's gateway log; the outcome above is graded without AI)`));
  } else dg.hidden = true;
  renderSupport(r);
  const ol = $("#timeline");
  ol.replaceChildren();
  if (!r.timeline.length) ol.append(el("li", {}, "No calls reached the gateway."));
  for (const e of r.timeline) {
    let text;
    if (e.kind === "search") text = `search ${e.status_code} via ${e.relay}${e.query ? `: “${e.query}”` : ""}${e.results != null ? ` → ${e.results} results` : ""}`;
    else text = `${e.kind} ${e.status} ${e.provider}/${e.model}${e.fallback_index ? " (fallback)" : ""}${e.tokens ? `, ${e.tokens} tokens` : ""}${e.error ? ` — ${e.error}` : ""}`;
    ol.append(el("li", { class: (e.status === "success" || (e.status_code && e.status_code < 400)) ? "ok" : "bad" },
      el("span", { class: "t" }, e.t.slice(11, 19) + " "), text));
  }
  const fetched = new Set((r.tavily.results || []).map((x) => normalize(x.url)));
  const div = $("#briefing");
  div.replaceChildren();
  const text = r.briefing || "";
  if (!text.trim()) { div.append(el("p", { class: "empty" }, "(no briefing written)")); }
  const re = /https?:\/\/[^\s<>"'\])}]+/gi;
  let last = 0, m;
  const pre = el("div", { class: "text" });
  while ((m = re.exec(text))) {
    pre.append(text.slice(last, m.index));
    const ok = fetched.has(normalize(m[0]));
    pre.append(el("a", { href: m[0], class: ok ? "ver" : "unver", target: "_blank", rel: "noopener noreferrer" }, m[0]));
    last = m.index + m[0].length;
  }
  pre.append(text.slice(last));
  div.append(pre);
  $("#run").scrollIntoView({ behavior: "smooth" });
}

function normalize(u) {
  try {
    u = u.replace(/[.,;:!?*_`'"]+$/, "");
    const x = new URL(u);
    for (const k of [...x.searchParams.keys()]) if (k.toLowerCase().startsWith("utm_")) x.searchParams.delete(k);
    x.hash = "";
    let s = x.protocol + "//" + x.host.toLowerCase() + x.pathname.replace(/\/+$/, "") + (x.search || "");
    return s;
  } catch { return u; }
}

function showStatus(text) {
  const st = $("#status");
  st.hidden = !text;
  st.textContent = text || "";
}

// Every state can be opened from the URL (?state=... or ?run=<run id>), so each can be checked
// and designed without clicking through. A state the data does not have says so; it is never faked.
const OUTCOME_STATES = {
  "run-pass": "PASS", "run-honest": "HONEST_FAIL", "run-thin": "WEAK", "run-silent": "SILENT_DEGRADE",
  "run-crash": "CRASH", "run-nothing": "NO_OUTPUT", "run-invalid": "INVALID",
};
const REAL_FIRST = (a, b) => CONTROLS.has(a.agent) - CONTROLS.has(b.agent);

function openState(params) {
  const state = params.get("state");
  const runId = params.get("run");
  const none = () => showStatus("No state like that in these results.");
  const run = (pred) => {
    const r = B.runs.filter(pred).sort(REAL_FIRST)[0];
    if (!r) return none();
    openCell(r.agent, r.condition);
    openRun(r);
  };
  if (runId) return run((r) => r.run_id === runId);
  if (!state || state === "overview") return;
  if (state === "cell") {
    const r = B.runs.filter((x) => x.condition === "baseline").sort(REAL_FIRST)[0];
    return r ? openCell(r.agent, r.condition) : none();
  }
  if (state === "notrun") {
    const cells = B.suite.summary.cells;
    for (const a of B.suite.agents) for (const c of B.suite.conditions) if (!(cells[a] || {})[c]) return openCell(a, c);
    return none();
  }
  if (OUTCOME_STATES[state]) return run((r) => r.grade.outcome === OUTCOME_STATES[state]);
  if (state === "run-planted") return run((r) => r.grade.echoed_planted_claim);
  if (state === "run-sourcecheck" || state === "result") return run((r) => (r.support || {}).items && r.support.items.length);
  none();
}

function start() {
  const params = new URLSearchParams(location.search);
  const state = params.get("state");
  if (state === "loading") return showStatus("Loading the results…");
  if (state === "error") return showStatus("The results could not be loaded (data/bundle.json). Reload the page, or build them with scripts/build_viewer.py.");
  showStatus("Loading the results…");
  fetch("data/bundle.json")
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((b) => {
      B = b;
      showStatus("");
      const s = b.suite;
      $("#meta").textContent = `${s.n_runs} runs · ${s.agents.length} agents · ${s.conditions.length} conditions · ` +
        `${s.tasks.length} briefing tasks · conditions run so far: ${s.conditions.map((c) => s.condition_labels[c] || c).join(", ")} · model held constant: ${s.model} · last run ${s.created.slice(0, 16).replace("T", " ")} UTC`;
      renderLeaderboard();
      renderMatrix();
      const m = $("#matrix");
      m.classList.add("reveal");
      if (window.design && design.onReplay) design.onReplay(() => { m.classList.remove("reveal"); void m.offsetWidth; m.classList.add("reveal"); });
      openState(params);
    })
    .catch(() => showStatus("The results could not be loaded (data/bundle.json). Reload the page, or build them with scripts/build_viewer.py."));
}

start();
