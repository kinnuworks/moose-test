#!/usr/bin/env python3
"""Bake the rendered leaderboard, matrix, stat tiles, pill and meta line into viewer/index.html,
so readers that run no JavaScript still see the results. The page renders them in a real browser
from data/bundle.json; this copies that markup into the file. app.js re-renders on load as before.

  scripts/prerender.py        (run after scripts/build_viewer.py)"""
import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWER = Path(__file__).resolve().parent.parent / "viewer"
PARTS = {  # element id -> what to copy
    "leaderboard": "tbody", "matrix": None, "tiles": None, "side-agents": None,
    "pill": None, "meta": None, "legend": None, "bignum": None,
}


def main():
    handler = partial(SimpleHTTPRequestHandler, directory=str(VIEWER))
    handler.log_message = lambda *a: None
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/?motion=reduce")
        page.wait_for_selector("#leaderboard tbody tr")
        got = page.evaluate("""(ids) => Object.fromEntries(Object.entries(ids).map(([id, sub]) => {
            const e = document.getElementById(id); if (!e) return [id, null];
            return [id, sub ? e.querySelector(sub).innerHTML : e.innerHTML]; }))""", PARTS)
        b.close()
    srv.shutdown()
    html = (VIEWER / "index.html").read_text()
    n_runs = json.loads((VIEWER / "data" / "bundle.json").read_text())["suite"]["n_runs"]

    def fill(html, id_, inner, sub=None):
        if inner is None:
            return html
        if sub == "tbody":
            pat = re.compile(r'(id="%s".*?<tbody>)(.*?)(</tbody>)' % re.escape(id_), re.S)
        else:
            pat = re.compile(r'(<(\w+)[^>]*\bid="%s"[^>]*>)(.*?)(</\2>)' % re.escape(id_), re.S)
            return pat.sub(lambda m: m.group(1) + inner + m.group(4), html, count=1)
        return pat.sub(lambda m: m.group(1) + inner + m.group(3), html, count=1)

    for id_, sub in PARTS.items():
        html = fill(html, id_, got[id_], sub)
    html = re.sub(r' hidden(?=[^>]*\bid="pill")|(?<=id="pill")([^>]*) hidden', lambda m: m.group(1) or "", html, count=1)
    html = re.sub(r'<body[^>]*>', f'<body data-baked-runs="{n_runs}">', html, count=1)
    (VIEWER / "index.html").write_text(html)
    print(f"baked {n_runs} runs into viewer/index.html")


if __name__ == "__main__":
    main()
