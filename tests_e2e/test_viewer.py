"""Walks the viewer's demo path in a real browser and records a video (the rough cut).
Written before the viewer."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer"
VIDEO_DIR = ROOT / "results" / "rough-cut"


def serve():
    handler = partial(SimpleHTTPRequestHandler, directory=str(VIEWER))
    handler.log_message = lambda *a: None
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_demo_path():
    bundle = json.loads((VIEWER / "data" / "bundle.json").read_text())
    agents = bundle["suite"]["agents"]
    srv, url = serve()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800},
                                  record_video_dir=str(VIDEO_DIR), record_video_size={"width": 1280, "height": 800})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        # first screen: the leaderboard from real committed results, no empty state
        expect(page.get_by_role("heading", name="Moose Test")).to_be_visible()
        rows = page.locator("#leaderboard tbody tr")
        expect(rows).to_have_count(len(agents))
        expect(page.locator("#meta")).to_contain_text(bundle["suite"]["model"])
        # the matrix has one cell per agent x condition
        cells = page.locator("#matrix td.cell")
        expect(cells).to_have_count(len(agents) * len(bundle["suite"]["conditions"]))
        # open a non-control agent's cell, then its first run
        real = [a for a in agents if a not in ("null",)][0]
        page.locator(f'#matrix td.cell[data-agent="{real}"]').first.click()
        page.locator("#runs li a").first.click()
        expect(page.locator("#run h3")).to_be_visible()
        expect(page.locator("#timeline li").first).to_be_visible()
        expect(page.locator("#briefing")).to_be_visible()
        # the AI source check: a leaderboard column, and on a passing run a labelled list of verdicts
        expect(page.locator("#leaderboard thead")).to_contain_text("Contradicted by source")
        checked = [r for r in bundle["runs"] if (r.get("support") or {}).get("items")]
        assert checked, "no run in the bundle has a source check"
        r = checked[0]
        page.locator(f'#matrix td.cell[data-agent="{r["agent"]}"][data-cond="{r["condition"]}"]').click()
        page.locator(f'#runs li a[href="#{r["run_id"]}"]').click()
        expect(page.locator("#support")).to_be_visible()
        expect(page.locator("#support")).to_contain_text("AI-written")
        expect(page.locator("#support li")).to_have_count(len(r["support"]["items"]))
        page.wait_for_timeout(800)
        ctx.close()
        browser.close()
    srv.shutdown()
    assert not errors, errors
