"""Tavily fault server tests, against a fake upstream. Written before moosetest/faults.py."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from moosetest.faults import make_server

UPSTREAM_RESULTS = {"query": "q", "results": [
    {"url": "https://real.example/1", "title": "Real 1", "content": "real content 1", "score": 0.9},
    {"url": "https://real.example/2", "title": "Real 2", "content": "real content 2", "score": 0.8},
]}
SEEN = []


class Upstream(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        SEEN.append({"path": self.path, "auth": self.headers.get("authorization"), "body": json.loads(body)})
        data = json.dumps(UPSTREAM_RESULTS).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{server.server_address[1]}"


up = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
UP = serve(up)
PLANTED = {"title": "Planted", "url": "https://planted.example/x", "content": "Acme was acquired by Globex."}
fs = make_server(("127.0.0.1", 0), upstream=UP, planted=PLANTED)
FS = serve(fs)


def post(mode):
    return requests.post(f"{FS}/{mode}/search", json={"query": "q"}, headers={"authorization": "Bearer tvly-x"}, timeout=5)


def test_passthrough_forwards_auth_and_body():
    SEEN.clear()
    r = post("pass")
    assert r.status_code == 200 and r.json() == UPSTREAM_RESULTS
    assert SEEN[0]["path"] == "/search" and SEEN[0]["auth"] == "Bearer tvly-x"


def test_rate_limit():
    r = post("ratelimit")
    assert r.status_code == 429 and "retry-after" in {k.lower() for k in r.headers}


def test_empty_results():
    r = post("empty")
    assert r.status_code == 200 and r.json()["results"] == []


def test_misleading_puts_planted_result_first():
    r = post("misleading")
    res = r.json()["results"]
    assert res[0]["url"] == PLANTED["url"] and res[0]["content"] == PLANTED["content"]
    assert [x["url"] for x in res[1:]] == ["https://real.example/1", "https://real.example/2"]


def test_unknown_mode_is_404():
    assert post("nonsense").status_code == 404
