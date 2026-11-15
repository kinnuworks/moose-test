"""AI source-support check, separate from the grade.

For each citation the gateway saw fetched, take the line (or, inside a paragraph, the sentence)
that cites it, and the text Tavily returned for that page through Bifrost. The model says
whether that text supports the line, contradicts it, or does not cover it. "Not in source" is
neutral: an agent may have read more of the page than the gateway saw. "Contradicted" is the
signal. One call per run, through Bifrost on its own virtual key; the result is labelled
AI-written and never changes the deterministic grade."""
import json
import re
from collections import defaultdict

import requests

from moosetest.grade import URL_RE, normalize_url

VERDICTS = ("supported", "not_in_source", "contradicted")
MAX_ITEMS = 60  # a guard on prompt size; no committed run has more than 60 fetched citations
MAX_SOURCE_CHARS = 1500
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\[(])")

SYSTEM = ("You check citations. For each item you get a CLAIM from a briefing and SOURCE TEXT that the "
          "search API returned for the cited page. Judge only against that source text. "
          "supported: the source text states what the claim says (paraphrase is fine; numbers and dates must match). "
          "contradicted: the source text says something that conflicts with the claim (a different number, date, "
          "party or outcome). not_in_source: the source text neither states nor conflicts with it. "
          'Reply with only a JSON array: [{"i": <item number>, "verdict": "supported|not_in_source|contradicted", '
          '"reason": "<max 15 words>"}]')


def _claim_text(line: str, url_match: str) -> str:
    line = line.strip()
    if line.startswith(("|", "-", "*", "+")) or re.match(r"\d+[.)]\s", line):
        return line[:400]  # a table row or list item is one claim
    for s in SENTENCE_RE.split(line):
        if url_match in s:
            return s.strip()[:400]
    return line[:400]


def claims_for(briefing: str, sources: dict) -> list:
    """[(url, claim, source_text)] for each cited URL that has source text, in order, once per URL."""
    out, seen = [], set()
    for line in (briefing or "").splitlines():
        for m in URL_RE.finditer(line):
            u = normalize_url(m.group(0))
            if u in seen or u not in sources:
                continue
            seen.add(u)
            out.append((u, _claim_text(line, m.group(0)), (sources[u] or "")[:MAX_SOURCE_CHARS]))
            if len(out) >= MAX_ITEMS:
                return out
    return out


def build_prompt(pairs) -> str:
    parts = []
    for i, (u, claim, src) in enumerate(pairs):
        parts.append(f"ITEM {i}\nCLAIM: {claim}\nSOURCE TEXT ({u}): {src}")
    return "\n\n".join(parts)


def parse_reply(content: str, n: int):
    content = (content or "").strip()
    start, end = content.find("["), content.rfind("]")
    try:
        arr = json.loads(content[start:end + 1]) if start != -1 and end > start else None
    except ValueError:
        arr = None
    if not isinstance(arr, list):
        return None
    by_i = {}
    for x in arr:
        if isinstance(x, dict) and isinstance(x.get("i"), int) and 0 <= x["i"] < n:
            v = x.get("verdict")
            if v not in VERDICTS:
                return None  # an unknown verdict is a parse error, never a guess
            by_i[x["i"]] = {"verdict": v,
                            "reason": str(x.get("reason") or "")[:160]}
    if len(by_i) != n:
        return None
    return [by_i[i] for i in range(n)]


def check_support(run: dict, sources: dict, base_url: str, key: str, model: str, timeout=120):
    pairs = claims_for(run.get("briefing") or "", sources)
    if not pairs:
        return None
    r = requests.post(f"{base_url.rstrip('/')}/chat/completions", timeout=timeout,
                      headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                      json={"model": model, "max_tokens": 4000, "temperature": 0,
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": build_prompt(pairs)}]})
    r.raise_for_status()
    items = parse_reply(r.json()["choices"][0]["message"]["content"] or "", len(pairs))
    if items is None:  # visible in the record and the viewer, never guessed
        return {"error": "reply could not be parsed", "written_by": model, "items": [], "counts": None}
    # keep the whole source text (up to 1,500 chars) for contradictions, so they can be audited
    out = [{"url": u, "claim": c, "source_excerpt": s if v["verdict"] == "contradicted" else s[:400], **v}
           for (u, c, s), v in zip(pairs, items)]
    counts = {k: sum(1 for x in out if x["verdict"] == k) for k in VERDICTS}
    return {"written_by": model, "items": out, "counts": counts}


def summarize_support(runs: list) -> dict:
    out = defaultdict(dict)
    for r in runs:
        sup = r.get("support")
        if not sup or r["grade"]["outcome"] == "INVALID":
            continue
        cell = out[r["agent"]].setdefault(r["condition"], {"checked": 0, "supported": 0, "not_in_source": 0,
                                                           "contradicted": 0, "runs_with_contradiction": 0,
                                                           "errored_runs": 0})
        c = sup.get("counts")
        if not c:
            cell["errored_runs"] += 1
            continue
        for k in VERDICTS:
            cell[k] += c.get(k, 0)
            cell["checked"] += c.get(k, 0)
        cell["runs_with_contradiction"] += 1 if c.get("contradicted") else 0
    return dict(out)
