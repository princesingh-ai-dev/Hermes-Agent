# hermes/tools/search.py
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools import WikipediaQueryRun
from tavily import TavilyClient
import httpx
from langchain_core.tools import tool
from hermes.tools.registry import register_tool

# DuckDuckGo and Wikipedia are already LangChain tools
try:
    ddg_search = DuckDuckGoSearchResults(num_results=5)
    register_tool(ddg_search)
except ImportError:
    print("Warning: Could not load DuckDuckGo tool. Please check your langchain-community and duckduckgo-search dependencies.")

wiki_search = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
register_tool(wiki_search)

@register_tool
@tool
async def jina_read(url: str) -> str:
    """Fetch and clean any URL via Jina Reader for free."""
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://r.jina.ai/{url}", timeout=30)
        return r.text
