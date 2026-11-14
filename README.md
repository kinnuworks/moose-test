# Moose Test

**Research agents, tested on their worst day.**

Moose Test runs open-source research agents exactly as they are published (GPT Researcher, LangChain's open_deep_research) on the same pre-meeting briefings, again and again, while the gateway takes away their model or breaks their web search. Every number comes from the gateway's own logs, not from the agents.

**Why Bifrost and Tavily:** the agents never know they are being tested. Their model calls go to [Bifrost](https://github.com/maximhq/bifrost) through an ordinary API key, which is a Bifrost virtual key. Their Tavily searches go through a Bifrost relay. So Bifrost can count every call, price it, inject the failure (a model outage, a rate-limited or empty search, a planted false result) and record exactly which pages each agent fetched. A citation counts only if the gateway saw the agent fetch that page.

<!-- GIF of a run timeline goes here -->

**Live results:** _link added after deploy_

## Try it in 30 seconds

Open the live results and click any cell in the "What each agent did" table, then a run. You see the gateway's timeline for that run and the briefing, with each cited link marked fetched or never fetched.

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

**How a run is graded** (`moosetest/grade.py`): PASS needs a real briefing (150+ words) with at least 3 citations that the gateway saw the agent fetch, and no more than 20% citations it never fetched. Honest failure means the agent said it could not do the job and invented nothing. Silent failure means the briefing looks fine but cites pages never fetched, cites nothing, or repeats the planted false claim. Two control agents run every time: `null` (writes nothing) and `single-search` (one search, one model call).

## Limits

- One model for all agents in a run, so results compare agents, not models.
- Briefing quality beyond citations (are the facts important?) is not scored. Citations are checked for having been fetched, not for whether the page supports the sentence.
- Tavily's `published_date` is its "best estimate", so recency shares are approximate and undated sources are counted separately.
- Bifrost logs are written asynchronously; the runner waits for them to settle before reading.

## Use of AI

The agents under test are AI research agents. The grader uses no AI: every outcome comes from deterministic checks against gateway logs. Parts of this repository were written with an AI coding assistant.
