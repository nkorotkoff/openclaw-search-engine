"""CLI entry point."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from .engine import run


@click.group()
def cli():
    """Scrapper Engine — stealth web scraper for OpenClaw."""
    pass


@cli.command()
@click.argument("query")
@click.option("-n", "--max-results", default=5, help="Search results to fetch from DDG.")
@click.option("-p", "--max-pages", default=3, help="Pages to actually scrape.")
@click.option("--follow-links", is_flag=True, help="Also scrape links found on pages.")
@click.option("--proxy", default=None, help="Proxy server (http://user:pass@host:port).")
@click.option("--no-headless", is_flag=True, help="Show browser window (debug).")
@click.option("--profile", default=None, help="Browser profile name (persists cookies).")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON output.")
def search(
    query: str,
    max_results: int,
    max_pages: int,
    follow_links: bool,
    proxy: str | None,
    no_headless: bool,
    profile: str | None,
    pretty: bool,
):
    """Search the web and extract page content as JSON.

    QUERY is the search string, e.g. "планшет до 10000 руб 10 дюймов".
    """
    result = asyncio.run(
        run(
            query=query,
            max_results=max_results,
            max_pages=max_pages,
            headless=not no_headless,
            proxy=proxy,
            profile=profile,
            follow_links=follow_links,
        )
    )
    indent = 2 if pretty else None
    json.dump(result, sys.stdout, ensure_ascii=False, indent=indent)
    sys.stdout.write("\n")


@cli.command()
@click.option("--url", default=None, help="Start by navigating to this URL.")
@click.option("--query", "-q", default=None, help="Start by searching DDG for this query.")
@click.option("--proxy", default=None, help="Proxy server.")
@click.option("--no-headless", is_flag=True, help="Show browser window.")
@click.option("--profile", default=None, help="Browser profile name (persists cookies).")
def interact(
    url: str | None,
    query: str | None,
    proxy: str | None,
    no_headless: bool,
    profile: str | None,
):
    """Interactive browser session. Send JSON commands via stdin.

    \b
    Commands:
      {"action": "goto", "url": "https://..."}
      {"action": "click", "index": 5}
      {"action": "type", "input_index": 0, "text": "hello", "submit": true}
      {"action": "scroll", "direction": "down"}
      {"action": "back"}
      {"action": "search", "query": "..."}
      {"action": "extract"}
      {"action": "screenshot", "path": "/tmp/screen.png"}
      {"action": "quit"}
    """
    from .interactive import interactive_session

    asyncio.run(
        interactive_session(
            start_url=url,
            start_query=query,
            headless=not no_headless,
            proxy=proxy,
            profile=profile,
        )
    )


def main():
    cli()


if __name__ == "__main__":
    main()
