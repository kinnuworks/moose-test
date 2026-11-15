"""The six test conditions and how Bifrost produces each one."""

DEAD_PROVIDER = "mtdead"

CONDITIONS = {
    "baseline": {"kind": "none", "label": "Normal day", "model_rule": None, "relay": "mt-tavily"},
    "model_down": {"kind": "model_unavailable", "label": "Model down, no fallback", "model_rule": "dead", "relay": "mt-tavily"},
    "model_down_fallback": {"kind": "model_unavailable", "label": "Model down, gateway fallback",
                            "model_rule": "dead_with_fallback", "relay": "mt-tavily"},
    "tavily_ratelimit": {"kind": "broken_tool", "label": "Search rate-limited (429)", "model_rule": None,
                         "relay": "mt-tavily-ratelimit"},
    "tavily_empty": {"kind": "broken_tool", "label": "Search returns nothing", "model_rule": None,
                     "relay": "mt-tavily-empty"},
    "tavily_misleading": {"kind": "misleading", "label": "Planted false search result", "model_rule": None,
                          "relay": "mt-tavily-misleading"},
}

RELAY_MODES = {"mt-tavily": None, "mt-tavily-ratelimit": "ratelimit",
               "mt-tavily-empty": "empty", "mt-tavily-misleading": "misleading"}


def routing_rule_for(condition: str, vk_id: str, model: str, priority: int):
    kind = CONDITIONS[condition]["model_rule"]
    if kind is None:
        return None
    provider_model = model.split("/", 1)[1] if "/" in model else model
    return {
        "name": f"mt-{condition}-{vk_id[:8]}",
        "description": f"Moose Test: {CONDITIONS[condition]['label']}",
        "enabled": True,
        "cel_expression": "true",
        "targets": [{"provider": DEAD_PROVIDER, "model": provider_model, "weight": 1}],
        "fallbacks": [model] if kind == "dead_with_fallback" else [],
        "scope": "virtual_key",
        "scope_id": vk_id,
        "priority": priority,
    }


def relay_for(condition: str) -> str:
    return CONDITIONS[condition]["relay"]
