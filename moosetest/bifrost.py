"""Small client for the Bifrost management API: providers, virtual keys, routing rules,
relays, and the LLM and relay logs the benchmark reads its numbers from."""
import os
import time

import requests


class BifrostError(RuntimeError):
    pass


class Bifrost:
    def __init__(self, base=None, user=None, password=None):
        self.base = (base or os.environ.get("BIFROST_URL", "http://localhost:8080")).rstrip("/")
        self.s = requests.Session()
        user = user or os.environ.get("BIFROST_ADMIN_USERNAME")
        password = password or os.environ.get("BIFROST_ADMIN_PASSWORD")
        if not (user and password):
            raise BifrostError("set BIFROST_ADMIN_USERNAME and BIFROST_ADMIN_PASSWORD")
        r = self.s.post(f"{self.base}/api/session/login", json={"username": user, "password": password}, timeout=15)
        if r.status_code != 200:
            raise BifrostError(f"login failed: {r.status_code} {r.text[:200]}")

    def _req(self, method, path, ok=(200, 201), **kw):
        r = self.s.request(method, f"{self.base}{path}", timeout=60, **kw)
        if r.status_code not in ok:
            raise BifrostError(f"{method} {path}: {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    # providers -----------------------------------------------------------
    def provider_keys(self, provider):
        r = self.s.get(f"{self.base}/api/providers/{provider}/keys", timeout=15)
        if r.status_code != 200:
            return []
        return r.json().get("keys") or []

    def ensure_custom_provider(self, name, base_url):
        """An OpenAI-compatible provider pointed at base_url (used for the dead provider)."""
        if not self.provider_keys(name):
            r = self.s.get(f"{self.base}/api/providers/{name}", timeout=15)
            if r.status_code != 200:
                self._req("POST", "/api/providers", json={
                    "provider": name, "custom_provider_config": {"base_provider_type": "openai"},
                    "network_config": {"base_url": base_url, "default_request_timeout_in_seconds": 5}})
            self._req("POST", f"/api/providers/{name}/keys",
                      json={"name": f"{name}-key", "value": "unused", "models": ["*"], "weight": 1})
        return self.provider_keys(name)

    # virtual keys --------------------------------------------------------
    def create_vk(self, name, provider_configs, relay_names=(), description=""):
        body = {"name": name, "description": description, "is_active": True,
                "provider_configs": provider_configs,
                "relay_grants": [{"relay_name": r} for r in relay_names]}
        return self._req("POST", "/api/governance/virtual-keys", json=body)["virtual_key"]

    def list_vks(self):
        d = self._req("GET", "/api/governance/virtual-keys")
        return d.get("virtual_keys") or d.get("data") or []

    def delete_vk(self, vk_id):
        self._req("DELETE", f"/api/governance/virtual-keys/{vk_id}", ok=(200, 204, 404))

    # routing rules -------------------------------------------------------
    def create_rule(self, rule):
        return self._req("POST", "/api/governance/routing-rules", json=rule).get("rule")

    def list_rules(self):
        d = self._req("GET", "/api/governance/routing-rules")
        return d.get("rules") or d.get("routing_rules") or d.get("data") or []

    def delete_rule(self, rule_id):
        self._req("DELETE", f"/api/governance/routing-rules/{rule_id}", ok=(200, 204, 404))

    # relays --------------------------------------------------------------
    def list_relays(self):
        d = self._req("GET", "/api/relays")
        return d.get("relays") or d.get("data") or []

    def delete_relay(self, name):
        self._req("DELETE", f"/api/relays/{name}", ok=(200, 204, 404))

    def ensure_relay(self, name, base_url, credential, routes=("/search", "/extract")):
        """(Re)create the relay so its base URL and credential always match this run."""
        if any(r.get("name") == name for r in self.list_relays()):
            self.delete_relay(name)
        self._req("POST", "/api/relays", json={
            "name": name, "base_url": base_url, "auth": {"type": "bearer"},
            "credential": {"value": credential},
            "routes": [{"method": "POST", "path": p} for p in routes]})

    # logs ----------------------------------------------------------------
    def _all_pages(self, path, params, page=500):
        """Read every page; the server reports total_count and may cap the page size."""
        out = []
        while True:
            d = self._req("GET", path, params={**params, "limit": page, "offset": len(out)})
            rows = d.get("logs") or []
            out.extend(rows)
            total = (d.get("pagination") or {}).get("total_count")
            if not rows or total is None or len(out) >= total:
                return out

    def llm_logs(self, vk_id):
        return self._all_pages("/api/logs", {"virtual_key_ids": vk_id})

    def llm_log(self, log_id):
        d = self._req("GET", f"/api/logs/{log_id}")
        return d.get("log", d)

    def relay_logs(self, vk_id=None):
        params = {"virtual_key_ids": vk_id} if vk_id else {}
        logs = self._all_pages("/api/relay-logs", params)
        # older builds ignore the filter; enforce it here
        return [l for l in logs if not vk_id or l.get("virtual_key_id") == vk_id]

    def relay_log(self, log_id):
        d = self._req("GET", f"/api/relay-logs/{log_id}")
        return d.get("log", d)

    def wait_for_logs(self, vk_id, min_rows=1, settle=6.0, timeout=60.0):
        """Log writes are asynchronous and batched; poll until at least min_rows exist
        and the counts have not changed for `settle` seconds."""
        last, stable_since, start = None, time.time(), time.time()
        while time.time() - start < timeout:
            cur = (len(self.llm_logs(vk_id)), len(self.relay_logs(vk_id)))
            if cur != last:
                last, stable_since = cur, time.time()
            elif time.time() - stable_since >= settle and sum(cur) >= min_rows:
                return cur
            time.sleep(1.0)
        return last
