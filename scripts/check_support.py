#!/usr/bin/env python3
"""Run the AI source-support check on stored runs that do not have one yet.

The page text each agent saw is read back from Bifrost's relay logs for that run's virtual
key, so this needs the same Bifrost the runs went through. The check goes through Bifrost on
its own virtual key. It never changes a grade.

  scripts/check_support.py results/suite-<tag>.json [...]"""
import json
import os
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from moosetest.bifrost import Bifrost  # noqa: E402
from moosetest.grade import grade_run, normalize_url  # noqa: E402
from moosetest.run import load_env_file  # noqa: E402
from moosetest.support import check_support  # noqa: E402


def sources_for(b, vk_id):
    out = {}
    for row in b.relay_logs(vk_id):
        d = b.relay_log(row["id"])
        try:
            body = json.loads(d.get("response_body") or "{}")
        except ValueError:
            continue  # a non-JSON reply (an injected 429, say) has no results to cite
        for x in body.get("results") or []:
            if x.get("url"):
                out[normalize_url(x["url"])] = (x.get("raw_content") or x.get("content") or "")[:1500]
    return out


def main(paths):
    load_env_file()
    b = Bifrost()
    vks = {v["name"]: v["id"] for v in b.list_vks()}
    model = json.loads(Path(paths[0]).read_text())["model"]
    provider, name = model.split("/", 1)
    vk = b.create_vk(f"mt-support-{secrets.token_hex(3)}",
                     [{"provider": provider, "allowed_models": [name], "weight": 1,
                       "key_ids": [k["id"] for k in b.provider_keys(provider)]}],
                     description="Moose Test source-support check")
    base = os.environ.get("BIFROST_URL", "http://localhost:8080").rstrip("/") + "/v1"
    todo = []
    for p in paths:
        suite = json.loads(Path(p).read_text())
        for rid in suite["runs"]:
            f = Path(p).parent / "runs" / f"{rid}.json"
            r = json.loads(f.read_text())
            r["grade"] = grade_run(r)
            if r.get("support") is not None or not r["grade"]["verified"] or r["grade"]["outcome"] == "INVALID":
                continue
            if r["virtual_key"] not in vks:
                print(f"no virtual key in Bifrost for {rid}; skipped (loud)", file=sys.stderr)
                continue
            todo.append((f, r))

    def one(item):
        f, r = item
        try:
            r["support"] = check_support(r, sources_for(b, vks[r["virtual_key"]]), base, vk["value"], model)
        except Exception as e:
            r["support"] = {"error": f"support check failed: {e}", "items": [], "counts": None}
        f.write_text(json.dumps(r, indent=1))
        return r["support"]

    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(one, todo))
    errors = sum(1 for s in res if s and s.get("error"))
    print(f"checked {len(res)} runs, {errors} errors")


if __name__ == "__main__":
    main(sys.argv[1:])
