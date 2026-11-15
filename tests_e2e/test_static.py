"""The live page must show its numbers to readers that run no JavaScript (link previews, text
fetchers, screen readers on slow devices): the leaderboard, matrix and stat tiles are baked into
index.html at build time from the same bundle. Written before scripts/prerender.py."""
import json
import re

from tests_e2e.test_viewer import VIEWER


def test_index_html_has_the_results_without_javascript():
    html = (VIEWER / "index.html").read_text()
    bundle = json.loads((VIEWER / "data" / "bundle.json").read_text())
    body = html[html.index('id="leaderboard"'):]
    tbody = body[body.index("<tbody>"):body.index("</tbody>")]
    assert tbody.count("<tr") == len(bundle["suite"]["agents"])
    for a in bundle["suite"]["agents"]:
        assert a in tbody
    m = html[html.index('id="matrix"'):]
    assert m[:m.index("</table>")].count('class="cell"') == len(bundle["suite"]["agents"]) * len(bundle["suite"]["conditions"])
    assert str(bundle["suite"]["n_runs"]) in html[html.index('id="tiles"'):html.index('id="tiles"') + 3000]
    # the baked copy matches the bundle it was built from
    assert re.search(r'data-baked-runs="%d"' % bundle["suite"]["n_runs"], html)


def test_index_html_has_one_run_step_by_step_without_javascript():
    # a judge or a text reader sees a single run's gateway timeline without clicking anything
    html = (VIEWER / "index.html").read_text()
    run = html[html.index('<section id="run"'):]
    run = run[:run.index("</section>")]
    assert "hidden" not in run[:run.index(">")]
    assert run.count("<li") >= 3 and "search 200" in run and "model success" in run


def test_baking_twice_gives_the_same_page():
    # the bake reads a clean template every time, so re-running it never nests or duplicates markup
    import subprocess, sys
    root = VIEWER.parent
    subprocess.run([sys.executable, "scripts/prerender.py"], cwd=root, check=True, capture_output=True)
    first = (VIEWER / "index.html").read_text()
    subprocess.run([sys.executable, "scripts/prerender.py"], cwd=root, check=True, capture_output=True)
    assert (VIEWER / "index.html").read_text() == first
    assert first.count('id="tiles"') == 1 and first.count('class="tile"') == 4
