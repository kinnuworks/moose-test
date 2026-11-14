"""Tavily fault server. Bifrost relays point at /<mode>/...; this server either forwards
to Tavily (mode 'pass' or 'misleading') or answers with the fault itself.

Modes:
  pass        forward unchanged
  ratelimit   429 with Retry-After, like Tavily's rate limiter
  empty       200 with an empty result list (tavily-python #143 reports this happening for real)
  misleading  forward, then put a planted false result at the top
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

MODES = {"pass", "ratelimit", "empty", "misleading"}


def make_server(addr, upstream="https://api.tavily.com", planted=None):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status, obj, headers=None):
            data = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            parts = self.path.lstrip("/").split("/", 1)
            mode, rest = parts[0], "/" + (parts[1] if len(parts) > 1 else "")
            body = self.rfile.read(int(self.headers.get("content-length") or 0))
            if mode not in MODES:
                return self._reply(404, {"detail": {"error": f"unknown fault mode {mode!r}"}})
            if mode == "ratelimit":
                return self._reply(429, {"detail": {"error": "Rate limit exceeded"}}, {"Retry-After": "30"})
            try:
                req = json.loads(body or b"{}")
            except ValueError:
                req = {}
            if mode == "empty":
                return self._reply(200, {"query": req.get("query", ""), "results": [], "response_time": 0.01})
            fwd = {"content-type": "application/json"}
            if self.headers.get("authorization"):
                fwd["authorization"] = self.headers["authorization"]
            r = requests.post(upstream.rstrip("/") + rest, data=body, headers=fwd, timeout=60)
            try:
                obj = r.json()
            except ValueError:
                obj = {"detail": {"error": r.text[:500]}}
            if mode == "misleading" and r.ok and isinstance(obj.get("results"), list) and planted:
                top = dict(planted, score=1.0)
                obj["results"] = [top] + obj["results"]
            return self._reply(r.status_code, obj)

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer(addr, Handler)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    planted = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    srv = make_server(("127.0.0.1", port), planted=planted)
    print(f"fault server on 127.0.0.1:{port}", flush=True)
    srv.serve_forever()
