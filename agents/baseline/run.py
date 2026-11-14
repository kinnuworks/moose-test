"""Control agent: one Tavily search, one model call. Uses the standard OpenAI and Tavily SDKs,
configured only by environment variables, like the real agents."""
import os
import sys

from openai import OpenAI
from tavily import TavilyClient

PROMPT = """Write a one-page pre-meeting briefing for this request:
{query}

Use only the search results below. Cite each fact with the URL it came from, in parentheses.
End with a section "Open questions" with three questions for the meeting.
If the results are empty or useless, say you could not find sources instead of guessing.

Search results:
{results}"""


def main(query: str, out: str):
    tv = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    res = tv.search(query, topic="news", time_range="month", max_results=8, include_published_date=True)
    lines = [f"- {r.get('title')} ({r.get('url')}) [{r.get('published_date') or 'undated'}]: {(r.get('content') or '')[:600]}"
             for r in res.get("results", [])]
    llm = OpenAI()
    msg = llm.chat.completions.create(
        model=os.environ["MOOSETEST_MODEL"],
        messages=[{"role": "user", "content": PROMPT.format(query=query, results="\n".join(lines) or "(none)")}],
        max_tokens=1500,
    )
    with open(out, "w") as f:
        f.write(msg.choices[0].message.content or "")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
