"""DuckDuckGo HTML search via httpx (no browser needed, avoids blocks)."""

from __future__ import annotations

import random

import httpx
from bs4 import BeautifulSoup

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_DDG_HTML = "https://html.duckduckgo.com/html/"


async def search_ddg(
    query: str,
    max_results: int = 10,
    proxy: str | None = None,
) -> list[dict]:
    """Search DuckDuckGo HTML-lite and return [{title, url, snippet}]."""
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
    }
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(
        follow_redirects=True,
        transport=transport,
        timeout=15.0,
    ) as client:
        resp = await client.post(
            _DDG_HTML,
            data={"q": query},
            headers=headers,
        )
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict] = []

    for a in soup.select(".result__a"):
        href = a.get("href", "")
        if not href.startswith("http"):
            continue
        title = a.get_text(strip=True)

        # Snippet is in the sibling .result__snippet
        parent = a.find_parent(class_="result")
        snippet = ""
        if parent:
            snip_el = parent.select_one(".result__snippet")
            if snip_el:
                snippet = snip_el.get_text(strip=True)

        results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= max_results:
            break

    return results
