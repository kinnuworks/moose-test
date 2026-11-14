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
