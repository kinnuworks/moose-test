"""Which Bifrost relay a proxied Tavily call goes to, chosen by the caller's virtual key.

A key that is not in the map, or a map that could not be read (None), goes to a relay that
does not exist, so Bifrost answers 404 and the run shows the failure. Sending it to the
baseline relay would quietly give a fault run real search results."""

UNMAPPED_RELAY = "mt-unmapped"


def relay_for_key(mapping, key):
    if not key or mapping is None:
        return UNMAPPED_RELAY
    return mapping.get(key, UNMAPPED_RELAY)
