"""Launch GPT Researcher as published (pip install gpt-researcher), using its documented API.
Configuration comes only from environment variables set by the runner."""
import asyncio
import sys


async def main(query: str, out: str):
    from gpt_researcher import GPTResearcher
    r = GPTResearcher(query=query, report_type="research_report")
    await r.conduct_research()
    report = await r.write_report()
    with open(out, "w") as f:
        f.write(report or "")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
