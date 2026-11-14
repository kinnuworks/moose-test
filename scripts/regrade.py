#!/usr/bin/env python3
"""Re-grade stored runs with the current grader, and re-diagnose any run whose outcome changed
or whose diagnosis is missing or unparsed. Diagnosis goes through Bifrost on its own key.

  scripts/regrade.py results/suite-<tag>.json [...]"""
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from moosetest.bifrost import Bifrost  # noqa: E402
from moosetest.diagnose import diagnose  # noqa: E402
from moosetest.grade import grade_run, summarize  # noqa: E402
from moosetest.run import load_env_file  # noqa: E402


def main(paths):
    load_env_file()
    b = Bifrost()
    vk = None
    changed = rediag = 0
    for p in paths:
        suite = json.loads(Path(p).read_text())
        model = suite["model"]
        provider, name = model.split("/", 1)
        if vk is None:
            keys = b.provider_keys(provider)
            vk = b.create_vk(f"mt-diagnosis-{secrets.token_hex(3)}",
                             [{"provider": provider, "allowed_models": [name], "weight": 1,
                               "key_ids": [k["id"] for k in keys]}], description="Moose Test failure diagnosis")
        runs = []
        for rid in suite["runs"]:
            f = Path(p).parent / "runs" / f"{rid}.json"
            r = json.loads(f.read_text())
            old = r["grade"]["outcome"]
            r["grade"] = grade_run(r)
            d = r.get("diagnosis") or {}
            if r["grade"]["outcome"] != old:
                changed += 1
            if r["grade"]["outcome"] == "PASS":
                r["diagnosis"] = None
            elif r["grade"]["outcome"] != old or not d or d.get("category") in ("unparsed", "error"):
                base = os.environ.get("BIFROST_URL", "http://localhost:8080").rstrip("/") + "/v1"
                try:
                    r["diagnosis"] = diagnose(r, base, vk["value"], model)
                except Exception as e:
                    r["diagnosis"] = {"diagnosis": f"diagnosis failed: {e}", "category": "error", "written_by": None}
                rediag += 1
            f.write_text(json.dumps(r, indent=1))
            runs.append(r)
        suite["summary"] = summarize(runs)
        Path(p).write_text(json.dumps(suite, indent=1))
    print(f"re-graded; {changed} outcomes changed, {rediag} diagnoses rewritten")


if __name__ == "__main__":
    main(sys.argv[1:])
