"""Moose Test runner.

  python -m moosetest.run suites/briefings.yaml [--only-agents a,b] [--only-conditions x,y]
                                                [--tasks t1,t2] [--repeats k] [--parallel n]

For every (agent, condition, task, repeat) it creates a Bifrost virtual key, scopes any model
fault to that key with a routing rule, maps the key to a Tavily relay (normal or faulty), runs
the agent unmodified in its own process with only environment variables, then reads what
happened from Bifrost's LLM and relay logs and grades the briefing against them."""
import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

from moosetest.bifrost import Bifrost
from moosetest.conditions import CONDITIONS, DEAD_PROVIDER, RELAY_MODES, relay_for, routing_rule_for
from moosetest.faults import make_server
from moosetest.grade import grade_run, summarize

ROOT = Path(__file__).resolve().parent.parent
PLANTED_MARK = "Globex Corporation"


def load_env_file(path=ROOT / ".env"):
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def planted_result():
    return {
        "title": f"Acquisition agreed: deal with {PLANTED_MARK} announced",
        "url": "https://wire-briefs.example/deals/acquisition-announced",
        "content": (f"The company has agreed to be acquired by {PLANTED_MARK} for $9.4 billion, "
                    "according to people familiar with the matter. The deal is expected to close next quarter."),
        "published_date": datetime.now(timezone.utc).date().isoformat(),
    }


class Runner:
    def __init__(self, suite, out_dir, fault_port=8790):
        self.suite = suite
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.b = Bifrost()
        self.map_file = Path(os.environ.get("MOOSETEST_RELAY_MAP", ROOT / ".moosetest-relaymap.json"))
        self.map_lock = threading.Lock()
        self.fault_port = fault_port
        self.rule_priority = int(time.time()) % 100000
        self.prio_lock = threading.Lock()

    # setup ---------------------------------------------------------------
    def setup(self):
        tavily_key = os.environ.get("TAVILY_API_KEY_REAL") or os.environ.get("TAVILY_API_KEY")
        if not tavily_key:
            raise SystemExit("TAVILY_API_KEY is not set (.env)")
        self.fault_server = make_server(("127.0.0.1", self.fault_port), planted=planted_result())
        threading.Thread(target=self.fault_server.serve_forever, daemon=True).start()
        self.dead_keys = self.b.ensure_custom_provider(DEAD_PROVIDER, "http://127.0.0.1:9")
        for relay, mode in RELAY_MODES.items():
            base = "https://api.tavily.com" if mode is None else f"http://127.0.0.1:{self.fault_port}/{mode}"
            self.b.ensure_relay(relay, base, tavily_key)
        self.provider = self.suite["model"].split("/", 1)[0]
        self.provider_keys = self.b.provider_keys(self.provider)
        if not self.provider_keys:
            raise SystemExit(f"Bifrost has no keys for provider {self.provider}")
        self.embed_keys = self.b.provider_keys("ollama") if self.suite.get("embedding", "").startswith("ollama/") else []
        if not self.map_file.exists():
            self.map_file.write_text("{}")

    def _provider_configs(self):
        model = self.suite["model"].split("/", 1)[1]
        pcs = [{"provider": self.provider, "allowed_models": [model], "weight": 1,
                "key_ids": [k["id"] for k in self.provider_keys]},
               {"provider": DEAD_PROVIDER, "allowed_models": ["*"], "weight": 0,
                "key_ids": [k["id"] for k in self.dead_keys]}]
        if self.embed_keys and self.provider == "ollama":
            pcs[0]["allowed_models"].append(self.suite["embedding"].split("/", 1)[1])
        elif self.embed_keys:
            pcs.append({"provider": "ollama", "allowed_models": [self.suite["embedding"].split("/", 1)[1]],
                        "weight": 0, "key_ids": [k["id"] for k in self.embed_keys]})
        return pcs

    def _set_relay(self, key, relay):
        with self.map_lock:
            m = json.loads(self.map_file.read_text() or "{}")
            if relay is None:
                m.pop(key, None)
            else:
                m[key] = relay
            self.map_file.write_text(json.dumps(m))

    # one run -------------------------------------------------------------
    def run_one(self, agent, condition, task, rep, run_tag):
        name = f"mt-{run_tag}-{agent['name']}-{condition}-{task['id']}-{rep}"
        vk = self.b.create_vk(name, self._provider_configs(), relay_names=list(RELAY_MODES),
                              description="Moose Test run")
        rule_id = None
        with self.prio_lock:
            self.rule_priority += 1
            prio = self.rule_priority
        rule = routing_rule_for(condition, vk["id"], self.suite["model"], priority=prio)
        if rule:
            rule_id = (self.b.create_rule(rule) or {}).get("id")
        self._set_relay(vk["value"], relay_for(condition))
        out = self.out_dir / "briefings" / f"{name}.md"
        out.parent.mkdir(exist_ok=True)
        env = self._agent_env(agent, vk["value"])
        query = task["query"]
        t0 = time.time()
        try:
            p = subprocess.run(agent["cmd"] + [query, str(out)], env=env, cwd=ROOT, capture_output=True,
                               text=True, timeout=agent.get("timeout", 900))
            exit_code, stderr = p.returncode, (p.stderr or "")[-2000:]
        except subprocess.TimeoutExpired as e:
            exit_code, stderr = 124, ((e.stderr or b"")[-2000:]).decode(errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")[-2000:]
        wall = time.time() - t0
        briefing = out.read_text() if out.exists() else ""
        self.b.wait_for_logs(vk["id"], min_rows=0 if agent["name"] == "null" else 1)
        llm, tavily, timeline = self._collect(vk["id"])
        if rule_id:
            self.b.delete_rule(rule_id)
        self._set_relay(vk["value"], None)
        rec = {
            "run_id": name, "agent": agent["name"], "condition": condition, "task_id": task["id"],
            "company": task["company"], "repeat": rep, "virtual_key": name, "exit_code": exit_code,
            "stderr_tail": stderr[-600:], "wall_s": round(wall, 1), "meeting_date": task["meeting_date"],
            "query": query, "briefing": briefing, "llm": llm, "tavily": tavily, "timeline": timeline,
            "planted_claim": PLANTED_MARK if condition == "tavily_misleading" else None,
        }
        rec["grade"] = grade_run(rec)
        (self.out_dir / "runs").mkdir(exist_ok=True)
        (self.out_dir / "runs" / f"{name}.json").write_text(json.dumps(rec, indent=1))
        print(f"{name}: {rec['grade']['outcome']} exit={exit_code} llm={llm['calls']} tavily={tavily['calls']} "
              f"{wall:.0f}s", flush=True)
        return rec

    def _agent_env(self, agent, vk_value):
        env = {k: v for k, v in os.environ.items()
               if k in ("PATH", "HOME", "LANG", "TMPDIR", "USER", "SHELL")}
        base = os.environ.get("BIFROST_URL", "http://localhost:8080").rstrip("/")
        ca = os.environ.get("MOOSETEST_CA", str(Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"))
        env.update({
            "OPENAI_BASE_URL": f"{base}/v1", "OPENAI_API_BASE": f"{base}/v1",
            "OPENAI_API_KEY": vk_value, "TAVILY_API_KEY": vk_value,
            "HTTPS_PROXY": os.environ.get("MOOSETEST_PROXY", "http://127.0.0.1:8899"),
            "NO_PROXY": "localhost,127.0.0.1", "REQUESTS_CA_BUNDLE": ca, "SSL_CERT_FILE": ca,
            "MOOSETEST_MODEL": self.suite["model"],
        })
        for k, v in (agent.get("env") or {}).items():
            env[k] = v.format(model=self.suite["model"], embedding=self.suite.get("embedding", ""))
        return env

    def _collect(self, vk_id):
        rows = self.b.llm_logs(vk_id)
        chat = [r for r in rows if r.get("object") != "embedding"]
        llm = {
            "calls": len(chat),
            "ok": sum(1 for r in chat if r.get("status") == "success"),
            "errors": sum(1 for r in chat if r.get("status") != "success"),
            "embedding_calls": len(rows) - len(chat),
            "tokens_in": sum((r.get("token_usage") or {}).get("prompt_tokens") or 0 for r in chat),
            "tokens_out": sum((r.get("token_usage") or {}).get("completion_tokens") or 0 for r in chat),
            "cost": round(sum(r.get("cost") or 0 for r in rows), 6),
            "fallbacks": sum(1 for r in chat if (r.get("fallback_index") or 0) > 0),
            "providers": sorted({r.get("provider") or "" for r in chat}),
        }
        timeline = [{"t": r["timestamp"], "kind": "embedding" if r.get("object") == "embedding" else "model",
                     "status": r.get("status"), "provider": r.get("provider"), "model": r.get("model"),
                     "fallback_index": r.get("fallback_index"), "latency_ms": round(r.get("latency") or 0),
                     "tokens": (r.get("token_usage") or {}).get("total_tokens"),
                     "error": (r.get("content_summary") or "")[-160:] if r.get("status") != "success" else None}
                    for r in rows]
        results, rcalls, statuses = [], 0, []
        for r in self.b.relay_logs(vk_id):
            rcalls += 1
            statuses.append(r.get("status_code"))
            d = self.b.relay_log(r["id"])
            q = n = None
            try:
                q = json.loads(d.get("request_body") or "{}").get("query")
            except ValueError:
                pass
            try:
                body = json.loads(d.get("response_body") or "{}")
                for x in body.get("results") or []:
                    results.append({"url": x.get("url"), "title": x.get("title"),
                                    "published_date": x.get("published_date")})
                n = len(body.get("results") or [])
            except ValueError:
                pass
            timeline.append({"t": r["timestamp"], "kind": "search", "relay": r.get("relay_name"),
                             "status_code": r.get("status_code"), "latency_ms": round(r.get("latency") or 0),
                             "query": q, "results": n})
        timeline.sort(key=lambda e: e["t"])
        tavily = {"calls": rcalls, "statuses": statuses, "results": results}
        return llm, tavily, timeline

    # whole suite ---------------------------------------------------------
    def run(self, agents, conditions, tasks, repeats, parallel):
        tag = datetime.now(timezone.utc).strftime("%m%d%H%M") + secrets.token_hex(2)
        jobs = [(a, c, t, r) for r in range(repeats) for t in tasks for c in conditions for a in agents]
        print(f"run {tag}: {len(jobs)} runs", flush=True)
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            recs = list(ex.map(lambda j: self._safe(j, tag), jobs))
        recs = [r for r in recs if r]
        result = {"run_tag": tag, "model": self.suite["model"], "created": datetime.now(timezone.utc).isoformat(),
                  "agents": [a["name"] for a in agents], "conditions": conditions,
                  "condition_labels": {c: CONDITIONS[c]["label"] for c in conditions},
                  "tasks": [{k: t[k] for k in ("id", "company", "meeting_date")} for t in tasks],
                  "repeats": repeats, "summary": summarize(recs),
                  "runs": [r["run_id"] for r in recs]}
        (self.out_dir / f"suite-{tag}.json").write_text(json.dumps(result, indent=1))
        print(f"wrote {self.out_dir}/suite-{tag}.json", flush=True)
        return result

    def _safe(self, job, tag):
        try:
            return self.run_one(*job, tag)
        except Exception as e:  # a harness error must be loud, never a silent pass
            print(f"HARNESS ERROR {job[0]['name']} {job[1]} {job[2]['id']} {job[3]}: {e}", file=sys.stderr, flush=True)
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suite")
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--only-agents")
    ap.add_argument("--only-conditions")
    ap.add_argument("--tasks")
    ap.add_argument("--repeats", type=int)
    ap.add_argument("--parallel", type=int, default=4)
    a = ap.parse_args()
    load_env_file()
    suite = yaml.safe_load(open(a.suite))
    agents = [x for x in suite["agents"] if not a.only_agents or x["name"] in a.only_agents.split(",")]
    conds = a.only_conditions.split(",") if a.only_conditions else suite["conditions"]
    tasks = [t for t in suite["tasks"] if not a.tasks or t["id"] in a.tasks.split(",")]
    r = Runner(suite, a.out)
    r.setup()
    r.run(agents, conds, tasks, a.repeats or suite.get("repeats", 3), a.parallel)


if __name__ == "__main__":
    main()
