"""mitmproxy addon: sends calls an agent makes to api.tavily.com through a Bifrost relay.

Agents keep their hard-coded Tavily URL. They get HTTPS_PROXY pointing here and a CA bundle
that trusts this proxy, and their TAVILY_API_KEY is their Bifrost virtual key. This addon
moves that key into the Authorization header Bifrost expects (removing it from the JSON body
so it is never forwarded or logged) and picks the relay for the key's test condition from
the map file the runner writes (MOOSETEST_RELAY_MAP)."""
import json
import os
import sys

from mitmproxy import http

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moosetest.proxy_map import relay_for_key  # noqa: E402

BIFROST_HOST = os.environ.get("BIFROST_HOST", "127.0.0.1")
BIFROST_PORT = int(os.environ.get("BIFROST_PORT", "8080"))
MAP_FILE = os.environ.get("MOOSETEST_RELAY_MAP", "")


def _mapping():
    """The runner replaces the map file atomically; None (unreadable) routes to an unknown relay."""
    try:
        with open(MAP_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def request(flow: http.HTTPFlow) -> None:
    if flow.request.pretty_host != "api.tavily.com":
        return
    key = None
    auth = flow.request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        key = auth[7:].strip()
    try:
        body = json.loads(flow.request.get_text() or "{}")
        if isinstance(body, dict) and "api_key" in body:
            key = key or body.pop("api_key")
            flow.request.set_text(json.dumps(body))
    except ValueError:
        pass
    relay = relay_for_key(_mapping(), key)
    path = flow.request.path
    flow.request.scheme, flow.request.host, flow.request.port = "http", BIFROST_HOST, BIFROST_PORT
    flow.request.path = f"/relay/{relay}{path}"
    flow.request.headers["host"] = f"{BIFROST_HOST}:{BIFROST_PORT}"
    if key:
        flow.request.headers["authorization"] = f"Bearer {key}"
