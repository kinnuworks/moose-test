"""Bifrost provisioning payloads and proxy routing. Written before the modules."""
from moosetest.conditions import CONDITIONS, routing_rule_for, relay_for
from moosetest.proxy_map import relay_for_key


def test_all_ps02_failure_kinds_covered():
    kinds = {c["kind"] for c in CONDITIONS.values()}
    assert {"none", "model_unavailable", "broken_tool", "misleading"} <= kinds


def test_model_down_rule_targets_dead_provider_with_no_fallback():
    rule = routing_rule_for("model_down", vk_id="vk-1", model="openai/gpt-4.1-mini", priority=3)
    assert rule["scope"] == "virtual_key" and rule["scope_id"] == "vk-1"
    assert rule["targets"][0]["provider"] == "mtdead"
    assert rule["fallbacks"] == []
    assert rule["cel_expression"] == "true"


def test_model_down_fallback_rule_falls_back_to_the_real_model():
    rule = routing_rule_for("model_down_fallback", vk_id="vk-1", model="openai/gpt-4.1-mini", priority=4)
    assert rule["fallbacks"] == ["openai/gpt-4.1-mini"]


def test_conditions_without_model_fault_have_no_rule():
    for c in ("baseline", "tavily_ratelimit", "tavily_empty", "tavily_misleading"):
        assert routing_rule_for(c, vk_id="v", model="m", priority=1) is None


def test_relay_per_condition():
    assert relay_for("baseline") == "mt-tavily"
    assert relay_for("model_down") == "mt-tavily"
    assert relay_for("tavily_ratelimit") == "mt-tavily-ratelimit"
    assert relay_for("tavily_empty") == "mt-tavily-empty"
    assert relay_for("tavily_misleading") == "mt-tavily-misleading"


def test_proxy_maps_key_to_relay_and_defaults_to_baseline():
    m = {"sk-bf-1": "mt-tavily-empty"}
    assert relay_for_key(m, "sk-bf-1") == "mt-tavily-empty"
    assert relay_for_key(m, "sk-bf-unknown") == "mt-tavily"
    assert relay_for_key(m, None) == "mt-tavily"


def test_collect_counts_only_real_provider_rate_limits():
    from moosetest.run import Runner
    from moosetest.conditions import DEAD_PROVIDER
    rows = ([{"id": "a", "status": "error", "provider": "anthropic", "timestamp": "t1"},
             {"id": "b", "status": "error", "provider": DEAD_PROVIDER, "timestamp": "t2"},
             {"id": "c", "status": "success", "provider": "anthropic", "timestamp": "t3"}])
    details = {"a": {"error_details": {"status_code": 429, "error": {"type": "rate_limit_error", "message": "limit"}}},
               "b": {"error_details": {"status_code": 429, "error": {"message": "x"}}}}

    class FakeB:
        def llm_logs(self, vk): return rows
        def llm_log(self, i): return details[i]
        def relay_logs(self, vk): return []
    r = object.__new__(Runner)
    r.b = FakeB()
    llm, _, timeline = r._collect("vk")
    assert llm["provider_rate_limited"] == 1
    assert any("429" in (e.get("error") or "") for e in timeline)


def test_invalid_runs_are_retried_and_agent_cap_holds(tmp_path, monkeypatch):
    import threading, time as _t
    import moosetest.run as mr
    monkeypatch.setattr(mr, "RETRY_WAIT_S", 0)
    r = object.__new__(mr.Runner)
    r.suite = {"model": "anthropic/m"}
    r.out_dir = tmp_path
    live, peak, lock, seen = {"heavy": 0}, {"heavy": 0}, threading.Lock(), []

    def fake_run_one(agent, cond, task, rep, tag, attempt=0):
        with lock:
            seen.append((agent["name"], attempt))
            if agent["name"] == "heavy":
                live["heavy"] += 1
                peak["heavy"] = max(peak["heavy"], live["heavy"])
        _t.sleep(0.02)
        with lock:
            if agent["name"] == "heavy":
                live["heavy"] -= 1
        out = "INVALID" if (agent["name"] == "heavy" and attempt == 0 and rep == 0) else "PASS"
        return {"run_id": f"{agent['name']}-{rep}-{attempt}", "agent": agent["name"], "condition": cond,
                "task_id": task["id"], "repeat": rep, "grade": {"outcome": out}, "llm": {}, "tavily": {}}
    r.run_one = fake_run_one
    agents = [{"name": "heavy", "max_parallel": 1}, {"name": "light"}]
    res = r.run(agents, ["baseline"], [{"id": "t1", "company": "X", "meeting_date": "2026-11-17"}], 4, 6)
    assert peak["heavy"] == 1
    assert ("heavy", 1) in seen and sum(1 for s in seen if s[1] == 1) == 1
    c = res["summary"]["cells"]["heavy"]["baseline"]
    assert c["n"] == 4 and c["pass"] == 4 and c["invalid"] == 1
