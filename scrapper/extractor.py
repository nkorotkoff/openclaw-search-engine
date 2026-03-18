"""Extract readable content from a web page."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page

from .browser import StealthBrowser

# Tags that usually contain useful content
_CONTENT_TAGS = {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "span", "div", "a"}
# Tags to strip completely
_STRIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"}


async def extract_page(page: Page, url: str, timeout: int = 20000) -> dict:
    """Navigate to url and extract structured content.

    Returns {url, title, text, links[]}.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except Exception as e:
        return {"url": url, "title": "", "text": "", "links": [], "error": str(e)}

    await StealthBrowser.human_delay(0.8, 1.5)

    html = await page.content()
    title = await page.title()

    soup = BeautifulSoup(html, "lxml")

    # Remove noise
    for tag_name in _STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Extract text blocks
    blocks: list[str] = []
    seen: set[str] = set()
    for el in soup.find_all(_CONTENT_TAGS):
        if not isinstance(el, Tag):
            continue
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 15:
            continue
        if text in seen:
            continue
        seen.add(text)
        blocks.append(text)

    # Extract links with text
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        if link_text and href.startswith("http"):
            links.append({"text": link_text, "url": href})

    full_text = "\n".join(blocks)
    # Truncate to avoid huge outputs
    if len(full_text) > 15000:
        full_text = full_text[:15000] + "\n...[truncated]"

    return {
        "url": url,
        "title": title,
        "text": full_text,
        "links": links[:50],
    }
