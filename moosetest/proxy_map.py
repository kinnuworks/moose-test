"""Which Bifrost relay a proxied Tavily call goes to, chosen by the caller's virtual key."""

DEFAULT_RELAY = "mt-tavily"


def relay_for_key(mapping: dict, key):
    if not key:
        return DEFAULT_RELAY
    return mapping.get(key, DEFAULT_RELAY)
