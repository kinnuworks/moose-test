#!/usr/bin/env python3
"""Bundle one suite run (summary + every run record) into viewer/data/bundle.json.

  scripts/build_viewer.py results/suite-<tag>.json [more suite files to merge...]

Merging lets a later run add repeats or agents to an earlier one; the summary is recomputed
from all included run records, never copied."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from moosetest.grade import grade_run, summarize  # noqa: E402


def main(paths):
    suites = [json.loads(Path(p).read_text()) for p in paths]
    runs, seen = [], set()
    for p, s in zip(paths, suites):
        run_dir = Path(p).parent / "runs"
        for rid in s["runs"]:
            if rid in seen:
                continue
            seen.add(rid)
            r = json.loads((run_dir / f"{rid}.json").read_text())
            r["grade"] = grade_run(r)  # always re-grade with the current grader
            r["briefing"] = (r.get("briefing") or "")[:20000]
            r["tavily"]["results"] = r["tavily"]["results"][:200]
            runs.append(r)
    first = suites[0]
    agents = list(dict.fromkeys(a for s in suites for a in s["agents"]))
    conds = list(dict.fromkeys(c for s in suites for c in s["conditions"]))
    labels = {}
    for s in suites:
        labels.update(s.get("condition_labels", {}))
    tasks = {t["id"]: t for s in suites for t in s["tasks"]}
    if len({s["model"] for s in suites}) != 1:
        raise SystemExit("refusing to merge runs made with different models")
    suite = {"model": first["model"], "agents": agents, "conditions": conds, "condition_labels": labels,
             "tasks": list(tasks.values()), "run_tags": [s["run_tag"] for s in suites],
             "created": max(s["created"] for s in suites), "n_runs": len(runs),
             "summary": summarize(runs)}
    out = ROOT / "viewer" / "data" / "bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"suite": suite, "runs": runs}))
    print(f"wrote {out} ({len(runs)} runs)")


if __name__ == "__main__":
    main(sys.argv[1:])
