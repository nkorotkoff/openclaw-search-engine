"""Main scraper engine: search → visit pages → extract → return JSON."""

from __future__ import annotations

from .browser import StealthBrowser
from .search import search_ddg
from .extractor import extract_page


async def run(
    query: str,
    max_results: int = 5,
    max_pages: int = 3,
    headless: bool = True,
    proxy: str | None = None,
    profile: str | None = None,
    follow_links: bool = False,
) -> dict:
    """Execute a full search-and-scrape pipeline.

    1. Search DuckDuckGo (via httpx, no browser)
    2. Open stealth browser and visit top result pages
    3. Extract content from each
    4. Return structured JSON
    """
    # Step 1: search (lightweight, no browser)
    search_results = await search_ddg(query, max_results=max_results, proxy=proxy)

    if not search_results:
        return {
            "query": query,
            "search_results": [],
            "pages": [],
            "error": "No search results found",
        }

    # Step 2: visit pages with stealth browser
    pages_data = []
    urls_to_visit = [r["url"] for r in search_results[:max_pages]]

    async with StealthBrowser(headless=headless, proxy=proxy, profile=profile) as browser:
        page = await browser.new_page()

        for url in urls_to_visit:
            await StealthBrowser.human_delay(1.0, 3.0)
            data = await extract_page(page, url)
            pages_data.append(data)

            if follow_links and data.get("links"):
                sub_links = [
                    l["url"]
                    for l in data["links"][:3]
                    if l["url"] not in urls_to_visit
                ]
                for sub_url in sub_links:
                    if len(pages_data) >= max_pages * 2:
                        break
                    await StealthBrowser.human_delay(1.0, 2.5)
                    sub_data = await extract_page(page, sub_url)
                    pages_data.append(sub_data)

        await page.close()

    return {
        "query": query,
        "search_results": search_results,
        "pages": pages_data,
    }
