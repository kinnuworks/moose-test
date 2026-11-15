# Moose Test

**Research agents, tested on their worst day.**

Moose Test runs open-source research agents exactly as they are published (GPT Researcher, LangChain's open_deep_research) on the same pre-meeting briefings, again and again, while the gateway takes away their model or breaks their web search. Every number comes from the gateway's own logs, not from the agents.

**Why Bifrost and Tavily:** the agents never know they are being tested. Their model calls go to [Bifrost](https://github.com/maximhq/bifrost) through an ordinary API key, which is a Bifrost virtual key. Their Tavily searches go through a Bifrost relay. So Bifrost can count every call, price it, inject the failure (a model outage, a rate-limited or empty search, a planted false result) and record exactly which pages each agent fetched. A citation counts only if the gateway saw the agent fetch that page.

<!-- GIF of a run timeline goes here -->

**Live results:** _link added after deploy_

## Try it in 30 seconds

Open the live results and click any cell in the "What each agent did" table, then a run. You see the gateway's timeline for that run and the briefing, with each cited link marked fetched or never fetched.

## What we found

433 runs on Claude Haiku 5.5, every agent on the same 8 briefing tasks, 3 times each (24 runs per cell). Pass rates have 95% Wilson intervals; with 24 out of 24, the interval is 0.86 to 1.00.

| Condition (injected by Bifrost) | GPT Researcher | open_deep_research | single-search (control) |
|---|---|---|---|
| Normal day | 24/24 pass, $0.0079 a run | not run yet | 24/24 pass, $0.0017 a run |
| Model down, Bifrost fallback on | 24/24 pass | not run yet | 23/24 pass, 1 too thin |
| Model down, no fallback | 24/24 crash after 120 requests and about 4.6 minutes | 24/24 crash after 9 requests and about 9 seconds | 24/24 crash |
| Tavily returns nothing | 24/24 say they found nothing | 24/24 say they found nothing | 24/24 say they found nothing |
| Tavily rate-limits (429) | 24/24 say they found nothing | 24/24 say they found nothing | 24/24 crash |
| A planted false result in the search | not run yet | not run yet | not run yet |

When search came back empty, both real agents told the truth. They differ in what that honesty cost. GPT Researcher stopped after 2 model calls and 5 searches, about 1,640 tokens. open_deep_research kept trying: 42 model calls, 50 searches, about 126,500 tokens, roughly 77 times as many for the same answer.

With the model gone and no fallback, GPT Researcher's own client kept retrying for about 4.6 minutes (120 requests, none of them retried by Bifrost) before it crashed. With Bifrost's fallback switched on, the same agent passed all 24 runs.

The `null` control writes nothing and is graded NO_OUTPUT every time, which checks that the grader cannot be passed by an empty run.

## Run it yourself

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
scripts/setup_agents.sh          # installs each agent under test, unmodified, in its own venv
echo "ANTHROPIC_API_KEY=..." >> .env && echo "TAVILY_API_KEY=..." >> .env
scripts/up.sh                    # Bifrost on :8080, Tavily proxy on :8899, Ollama for embeddings
.venv/bin/python -m moosetest.run suites/briefings.yaml --repeats 3
.venv/bin/python scripts/build_viewer.py results/suite-*.json && python3 -m http.server -d viewer
```

## How it works

| Requirement | How Moose Test meets it |
|---|---|
| Framework independence | Agents run as published, in their own processes, configured only by environment variables: `OPENAI_BASE_URL` (Bifrost), `OPENAI_API_KEY` (a Bifrost virtual key), `TAVILY_API_KEY` (the same key) and a standard `HTTPS_PROXY` that sends their hard-coded Tavily calls to a Bifrost relay. No agent code is edited or wrapped. |
| Consistent evaluation | Same tasks for every agent, same model for every agent. Success, model calls, search calls, tokens, cost and wall time per run, read from Bifrost's LLM and relay logs for that run's virtual key. |
| Repeatability | Every (agent, condition, task) runs k times. Reported as pass rate with a 95% Wilson interval and pass^k (every repeat passed). |
| Failure testing | Model outage (a Bifrost routing rule scoped to the run's key sends calls to a dead provider), the same outage with a Bifrost fallback, Tavily rate limit (429), Tavily empty results, and a planted false search result, each injected at the gateway. |
| Inspection and comparison | A static viewer: leaderboard, agent × condition matrix, and per-run timelines built from gateway log rows next to the briefing. |

Bifrost also keeps the test fair. Our model account has per-minute and concurrency limits, and open_deep_research at its defaults sent about 320 model calls in one minute. The suite sets Bifrost's provider queue (8 requests in flight, the rest wait) and retries the provider's 429s with backoff, the same for every agent. Injected outages go to a separate dead provider, so this queue never hides them. A run that still hits our own account's limit, or fails before any request reaches Bifrost, is marked INVALID, kept on disk, left out of every score and run again.

**How a run is graded** (`moosetest/grade.py`): PASS needs a real briefing (150+ words) with at least 3 citations that the gateway saw the agent fetch, and no more than 20% citations it never fetched. Honest failure means the agent said it could not do the job and invented nothing. Silent failure means the briefing looks fine but cites pages never fetched, cites nothing, or repeats the planted false claim. Two control agents run every time: `null` (writes nothing) and `single-search` (one search, one model call).

## Limits

- One model for all agents in a run, so results compare agents, not models.
- Briefing quality beyond citations (are the facts important?) is not scored. Citations are checked for having been fetched, not for whether the page supports the sentence.
- Tavily's `published_date` is its "best estimate", so recency shares are approximate and undated sources are counted separately.
- Bifrost logs are written asynchronously; the runner waits for them to settle before reading.

## Use of AI

The agents under test are AI research agents. The grader uses no AI: every outcome comes from deterministic checks against gateway logs. For each run that did not pass, the model writes one sentence saying what went wrong, from that run's gateway timeline; the viewer labels it as AI-written, and it never changes the grade. Parts of this repository were written with an AI coding assistant.
