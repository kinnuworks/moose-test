"""AI source-support check: does the text the gateway saw for a cited page back the line that
cites it? Written before moosetest/support.py. Separate from the grade, labelled AI-written."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from moosetest.support import claims_for, check_support, parse_reply, summarize_support

BRIEF = """# Briefing
- Stripe launched stablecoin payouts in 160 markets. (https://news.example/a)
- Link integrates with MiniPay. (https://news.example/b?utm_source=x)

| Date | Event | Source |
|---|---|---|
| 1 Nov | 22 acquisitions | [Tracxn](https://tracxn.example/c) |
A paragraph with two sentences. Revenue grew 30% in 2025 (https://news.example/d). Unrelated closing sentence.
- Never fetched claim (https://made-up.example/z)
"""
SOURCES = {
    "https://news.example/a": "Stripe now lets businesses send stablecoin payouts in more than 160 markets.",
    "https://news.example/b": "Celo MiniPay integrates Link by Stripe.",
    "https://tracxn.example/c": "Stripe has made 22 acquisitions.",
    "https://news.example/d": "Revenue fell in 2025.",
}


def test_claims_are_the_citing_line_or_sentence_and_only_for_fetched_urls():
    pairs = claims_for(BRIEF, SOURCES)
    urls = [u for u, _, _ in pairs]
    assert urls == ["https://news.example/a", "https://news.example/b", "https://tracxn.example/c", "https://news.example/d"]
    claim_d = pairs[3][1]
    assert "Revenue grew 30%" in claim_d and "Unrelated closing" not in claim_d
    assert pairs[2][1].startswith("| 1 Nov")
    assert pairs[0][2] == SOURCES["https://news.example/a"]


CALLS = []


class FakeChat(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        CALLS.append({"auth": self.headers.get("authorization"), "body": body})
        verdicts = [{"i": 0, "verdict": "supported", "reason": "160 markets stated"},
                    {"i": 1, "verdict": "supported", "reason": "integration stated"},
                    {"i": 2, "verdict": "supported", "reason": "22 acquisitions"},
                    {"i": 3, "verdict": "contradicted", "reason": "source says revenue fell"}]
        data = json.dumps({"choices": [{"message": {"content": "```json\n" + json.dumps(verdicts) + "\n```"}}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeChat)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/v1"


def test_check_support_goes_through_the_gateway_and_keeps_grade():
    CALLS.clear()
    run = {"briefing": BRIEF, "grade": {"outcome": "PASS"}}
    before = json.dumps(run["grade"])
    s = check_support(run, SOURCES, BASE, "sk-bf-support", "anthropic/m")
    assert CALLS and CALLS[0]["auth"] == "Bearer sk-bf-support"
    assert s["written_by"] == "anthropic/m"
    assert s["counts"] == {"supported": 3, "not_in_source": 0, "contradicted": 1}
    assert s["items"][3]["verdict"] == "contradicted" and s["items"][3]["url"] == "https://news.example/d"
    assert json.dumps(run["grade"]) == before


def test_no_fetched_citations_means_no_call():
    CALLS.clear()
    assert check_support({"briefing": "No sources found."}, {}, BASE, "k", "m") is None
    assert not CALLS


def test_bad_reply_is_reported_not_hidden():
    items = parse_reply("not json", 2)
    assert items is None


def test_unknown_verdict_is_a_parse_error_not_a_quiet_not_in_source():
    # review found the old behaviour turned an unknown verdict into "not_in_source" silently
    items = parse_reply('[{"i": 0, "verdict": "maybe", "reason": "x"}, {"i": 1, "verdict": "contradicted", "reason": "y"}]', 2)
    assert items is None


def test_summary_over_runs():
    runs = [{"agent": "a", "condition": "baseline", "grade": {"outcome": "PASS"},
             "support": {"counts": {"supported": 3, "not_in_source": 1, "contradicted": 0}}},
            {"agent": "a", "condition": "baseline", "grade": {"outcome": "PASS"},
             "support": {"counts": {"supported": 1, "not_in_source": 0, "contradicted": 1}}},
            {"agent": "a", "condition": "baseline", "grade": {"outcome": "INVALID"},
             "support": {"counts": {"supported": 9, "not_in_source": 0, "contradicted": 9}}}]
    s = summarize_support(runs)["a"]["baseline"]
    assert s == {"checked": 6, "supported": 4, "not_in_source": 1, "contradicted": 1, "runs_with_contradiction": 1,
                 "errored_runs": 0}


def test_errored_checks_are_counted_in_the_summary():
    runs = [{"agent": "a", "condition": "baseline", "grade": {"outcome": "PASS"},
             "support": {"error": "reply could not be parsed", "counts": None, "items": []}},
            {"agent": "a", "condition": "baseline", "grade": {"outcome": "PASS"},
             "support": {"counts": {"supported": 2, "not_in_source": 0, "contradicted": 0}}}]
    s = summarize_support(runs)["a"]["baseline"]
    assert s["errored_runs"] == 1 and s["checked"] == 2


def test_every_fetched_citation_is_checked_not_only_the_first_twelve():
    lines = "\n".join(f"- claim {i} (https://n.example/{i})" for i in range(30))
    sources = {f"https://n.example/{i}": "text" for i in range(30)}
    assert len(claims_for(lines, sources)) == 30
