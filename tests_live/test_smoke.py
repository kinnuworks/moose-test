"""Live smoke test against the real stack: local Bifrost, the real model provider and real Tavily.
No mocks. Runs the control agent and GPT Researcher on one task under three conditions."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "smoke"


def env_file():
    p = ROOT / ".env"
    vals = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def test_live_smoke():
    vals = env_file()
    # report key NAMES only; never let an assertion print secret values
    missing = sorted(k for k in ("TAVILY_API_KEY", "ANTHROPIC_API_KEY") if not vals.get(k))
    assert not missing, "missing in .env (the live check needs the real model and real Tavily)"
    p = subprocess.run(
        [sys.executable, "-m", "moosetest.run", "suites/briefings.yaml", "--out", str(OUT),
         "--only-agents", "single-search,gpt-researcher", "--only-conditions",
         "baseline,model_down_fallback,tavily_empty", "--tasks", "t1", "--repeats", "1", "--parallel", "6"],
        cwd=ROOT, capture_output=True, text=True, timeout=1500, env={**os.environ, **vals})
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    suite_file = sorted(OUT.glob("suite-*.json"))[-1]
    suite = json.loads(suite_file.read_text())
    runs = {}
    for rid in suite["runs"]:
        r = json.loads((OUT / "runs" / f"{rid}.json").read_text())
        runs[(r["agent"], r["condition"])] = r
    assert len(runs) == 6
    # every run reached the gateway, and its numbers come from gateway logs
    for (agent, cond), r in runs.items():
        assert r["llm"]["calls"] + r["tavily"]["calls"] > 0, (agent, cond, "no gateway rows")
    # on a normal day the control agent writes a briefing citing pages it really fetched
    base = runs[("single-search", "baseline")]
    assert base["tavily"]["calls"] >= 1 and base["tavily"]["results"], "no real Tavily results through the relay"
    assert base["grade"]["verified"] >= 1, base["grade"]
    # the gateway really served model-down runs from the fallback
    for agent in ("single-search", "gpt-researcher"):
        fb = runs[(agent, "model_down_fallback")]
        assert fb["llm"]["fallbacks"] >= 1, (agent, "no fallback seen in gateway logs", fb["llm"])
    # the empty-search fault really reached the agents through the gateway
    for agent in ("single-search", "gpt-researcher"):
        em = runs[(agent, "tavily_empty")]
        assert em["tavily"]["calls"] >= 1 and not em["tavily"]["results"], (agent, em["tavily"])
