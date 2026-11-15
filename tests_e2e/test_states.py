"""Every viewer state can be opened directly with ?state=, so each one can be checked and
designed without clicking through. Written before the ?state= support in viewer/app.js."""
import json

from playwright.sync_api import expect, sync_playwright

from tests_e2e.test_viewer import VIEWER, serve

OUTCOME_STATES = {
    "run-pass": "PASS", "run-honest": "HONEST_FAIL", "run-thin": "WEAK", "run-silent": "SILENT_DEGRADE",
    "run-crash": "CRASH", "run-nothing": "NO_OUTPUT", "run-invalid": "INVALID",
}


def test_every_state_opens_from_the_url():
    bundle = json.loads((VIEWER / "data" / "bundle.json").read_text())
    runs = bundle["runs"]
    srv, url = serve()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(url + "/?state=loading")
        expect(page.locator("#status")).to_contain_text("Loading")
        expect(page.locator("#leaderboard tbody tr")).to_have_count(0)

        page.goto(url + "/?state=error")
        expect(page.locator("#status")).to_contain_text("could not be loaded")

        page.goto(url + "/?state=overview")
        expect(page.locator("#leaderboard tbody tr")).to_have_count(len(bundle["suite"]["agents"]))
        expect(page.locator("#status")).to_be_hidden()

        page.goto(url + "/?state=cell")
        expect(page.locator("#drill")).to_be_visible()
        expect(page.locator("#runs li").first).to_be_visible()

        # a cell with no runs says so instead of showing an empty list
        cells = bundle["suite"]["summary"]["cells"]
        missing = [(a, c) for a in bundle["suite"]["agents"] for c in bundle["suite"]["conditions"]
                   if c not in cells.get(a, {})]
        page.goto(url + "/?state=notrun")
        if missing:
            expect(page.locator("#drill")).to_contain_text("Not run yet")
        else:
            expect(page.locator("#status")).to_contain_text("No state like that in these results")

        for state, outcome in OUTCOME_STATES.items():
            page.goto(url + f"/?state={state}")
            if any(r["grade"]["outcome"] == outcome for r in runs):
                expect(page.locator("#run h3")).to_be_visible()
                expect(page.locator("#run-facts")).to_contain_text("Outcome:")
            else:
                expect(page.locator("#status")).to_contain_text("No state like that in these results")

        planted = [r for r in runs if r["grade"].get("echoed_planted_claim")]
        page.goto(url + "/?state=run-planted")
        if planted:
            expect(page.locator("#run-facts")).to_contain_text("planted false claim")

        checked = [r for r in runs if (r.get("support") or {}).get("items")]
        page.goto(url + "/?state=run-sourcecheck")
        expect(page.locator("#support li")).to_have_count(len(checked[0]["support"]["items"]))

        # "result" is the design tools' name for the finished-result screen: a run with its source check
        page.goto(url + "/?state=result")
        expect(page.locator("#support li").first).to_be_visible()

        page.goto(url + f"/?run={runs[0]['run_id']}")
        expect(page.locator("#run h3")).to_contain_text(runs[0]["agent"])

        page.goto(url + "/?state=nonsense")
        expect(page.locator("#status")).to_contain_text("No state like that in these results")
        browser.close()
    srv.shutdown()
    assert not errors, errors
