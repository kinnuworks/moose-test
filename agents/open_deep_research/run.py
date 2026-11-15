"""Launch LangChain open_deep_research as published, through its documented graph and
`configurable` options. Only the model names are set (all to the suite's model, so every agent
runs on the same model); search stays on its default, Tavily. Keys and endpoints come from
environment variables set by the runner. The suite may set its documented
max_concurrent_research_units (ODR_MAX_CONCURRENT_RESEARCH_UNITS): at the default of 5 one run
sent about 300 model calls in a minute, over our provider account's input-token limit."""
import asyncio
import os
import sys


async def main(query: str, out: str):
    from open_deep_research.deep_researcher import deep_researcher
    model = "openai:" + os.environ["MOOSETEST_MODEL"]
    config = {"configurable": {
        "allow_clarification": False,
        "search_api": "tavily",
        "research_model": model, "summarization_model": model,
        "compression_model": model, "final_report_model": model,
    }}
    if os.environ.get("ODR_MAX_CONCURRENT_RESEARCH_UNITS"):
        config["configurable"]["max_concurrent_research_units"] = int(os.environ["ODR_MAX_CONCURRENT_RESEARCH_UNITS"])
    result = await deep_researcher.ainvoke({"messages": [{"role": "user", "content": query}]}, config)
    report = result.get("final_report") or ""
    with open(out, "w") as f:
        f.write(report)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
