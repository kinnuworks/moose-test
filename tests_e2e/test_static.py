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
