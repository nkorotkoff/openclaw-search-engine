"""Stealth browser manager using Camoufox (modified Firefox with anti-detect)."""

import asyncio
import random
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from camoufox.async_api import AsyncNewBrowser


# Persistent profiles directory
PROFILES_DIR = Path.home() / ".scrapper_engine" / "profiles"


class StealthBrowser:
    """Manages a stealth Camoufox browser instance.

    Uses camoufox — a modified Firefox build that patches all major
    fingerprinting vectors: canvas, WebGL, fonts, navigator properties,
    AudioContext, etc. Combined with persistent profiles (cookies survive
    between runs) this defeats most antibot systems including Ozon, WB, etc.
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: str | None = None,
        profile: str | None = None,
    ):
        self._headless = headless
        self._proxy = proxy
        self._profile = profile
        self._pw = None
        self._browser: Browser | BrowserContext | None = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()

        kwargs: dict = {
            "humanize": True,
            "locale": "ru-RU",
            "block_webrtc": True,
            "enable_cache": True,
        }

        if self._proxy:
            kwargs["proxy"] = {"server": self._proxy}

        # Use persistent context if profile is specified
        if self._profile:
            profile_dir = PROFILES_DIR / self._profile
            profile_dir.mkdir(parents=True, exist_ok=True)
            kwargs["persistent_context"] = True
            kwargs["firefox_user_prefs"] = {
                "profile": str(profile_dir),
            }

        self._browser = await AsyncNewBrowser(
            self._pw,
            headless=self._headless,
            **kwargs,
        )
        return self

    async def __aexit__(self, *exc):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def new_page(self) -> Page:
        # If persistent_context, self._browser is already a BrowserContext
        if isinstance(self._browser, BrowserContext):
            page = await self._browser.new_page()
        else:
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            page = await context.new_page()
        return page

    @staticmethod
    async def human_delay(lo: float = 0.5, hi: float = 2.0):
        await asyncio.sleep(random.uniform(lo, hi))
