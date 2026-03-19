"""Interactive browser session: REPL for weak models.

The model sends JSON commands via stdin, gets JSON responses on stdout.
Clickable elements are numbered so the model can say "click 5".
"""

from __future__ import annotations

import asyncio
import json
import sys

from playwright.async_api import Page, Dialog
from bs4 import BeautifulSoup, Tag

from .browser import StealthBrowser
from .extractor import _wait_for_content


def _extract_interactive(html: str, title: str, url: str) -> dict:
    """Extract page content with numbered interactive elements."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noise
    for tag_name in ("script", "style", "noscript", "svg"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Collect clickable elements with indices
    elements: list[dict] = []
    idx = 0

    # Links
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a.get("href", "")
        if text and len(text) > 2:
            elements.append({
                "index": idx,
                "type": "link",
                "text": text[:120],
                "href": href,
            })
            idx += 1

    # Buttons
    for btn in soup.find_all(["button", "input"]):
        if btn.name == "input" and btn.get("type") not in ("submit", "button", "search"):
            continue
        text = btn.get_text(strip=True) or btn.get("value", "") or btn.get("aria-label", "")
        if text:
            elements.append({
                "index": idx,
                "type": "button",
                "text": text[:120],
            })
            idx += 1

    # Clickable divs/spans (role="button", onclick, etc.)
    for el in soup.find_all(attrs={"role": "button"}):
        if el.name in ("a", "button", "input"):
            continue
        text = el.get_text(strip=True)
        if text and len(text) > 2:
            elements.append({
                "index": idx,
                "type": "role-button",
                "text": text[:120],
            })
            idx += 1

    # Tabs, menu items
    for el in soup.find_all(attrs={"role": ["tab", "menuitem", "option", "listbox"]}):
        text = el.get_text(strip=True)
        if text and len(text) > 1:
            elements.append({
                "index": idx,
                "type": el.get("role", "interactive"),
                "text": text[:120],
            })
            idx += 1

    # Input fields
    inputs: list[dict] = []
    input_idx = 0
    for inp in soup.find_all(["input", "textarea", "select"]):
        if inp.name == "input" and inp.get("type") in ("hidden", "submit", "button"):
            continue
        name = inp.get("name", "")
        placeholder = inp.get("placeholder", "")
        inp_type = inp.get("type", inp.name)
        label_text = name or placeholder or inp.get("aria-label", "") or inp.get("id", "")
        value = inp.get("value", "")

        entry: dict = {
            "index": input_idx,
            "type": inp_type,
            "name": name,
            "placeholder": placeholder,
            "label": label_text[:80],
            "value": value[:80] if value else "",
        }

        # For <select>, include available options
        if inp.name == "select":
            options = []
            for opt in inp.find_all("option"):
                opt_val = opt.get("value", "")
                opt_text = opt.get_text(strip=True)
                selected = opt.has_attr("selected")
                options.append({
                    "value": opt_val,
                    "text": opt_text[:60],
                    "selected": selected,
                })
            entry["options"] = options[:30]

        if label_text or inp.name == "select":
            inputs.append(entry)
            input_idx += 1

    # Text content (compact)
    blocks: list[str] = []
    seen: set[str] = set()
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "td", "th", "span", "div", "label"]):
        if not isinstance(el, Tag):
            continue
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 10 or text in seen:
            continue
        seen.add(text)
        blocks.append(text)

    full_text = "\n".join(blocks)
    if len(full_text) > 15000:
        full_text = full_text[:15000] + "\n...[truncated]"

    return {
        "url": url,
        "title": title,
        "text": full_text,
        "elements": elements[:150],
        "inputs": inputs[:30],
    }


async def _get_page_state(page: Page) -> dict:
    """Get current page state with interactive elements."""
    html = await page.content()
    title = await page.title()
    url = page.url
    return _extract_interactive(html, title, url)


async def _collect_visible_clickables(page: Page) -> list:
    """Collect visible clickable elements in DOM order, matching _extract_interactive indices."""
    clickables = await page.query_selector_all(
        'a[href], button, input[type="submit"], input[type="button"], '
        'input[type="search"], [role="button"], [role="tab"], [role="menuitem"]'
    )
    visible = []
    for el in clickables:
        try:
            if not await el.is_visible():
                continue
            text = ""
            try:
                text = (await el.inner_text() or "").strip()
            except Exception:
                pass
            if not text:
                text = (
                    await el.get_attribute("value")
                    or await el.get_attribute("aria-label")
                    or await el.get_attribute("title")
                    or ""
                ).strip()
            if text and len(text) > 1:
                visible.append(el)
        except Exception:
            continue
    return visible


async def _collect_visible_inputs(page: Page) -> list:
    """Collect visible input elements in DOM order."""
    inputs = await page.query_selector_all(
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), '
        "textarea, select"
    )
    visible = []
    for inp in inputs:
        try:
            if await inp.is_visible():
                visible.append(inp)
        except Exception:
            continue
    return visible


async def interactive_session(
    start_url: str | None = None,
    start_query: str | None = None,
    headless: bool = True,
    proxy: str | None = None,
    profile: str | None = None,
):
    """Run an interactive browser session.

    Commands (JSON on stdin):
        {"action": "goto", "url": "https://..."}
        {"action": "click", "index": 5}
        {"action": "type", "input_index": 0, "text": "hello"}
        {"action": "select", "input_index": 2, "value": "option_value"}
        {"action": "scroll", "direction": "down"}
        {"action": "hover", "index": 5}
        {"action": "press_key", "key": "Tab"}
        {"action": "wait", "ms": 3000}
        {"action": "wait_for", "text": "Найдено"}
        {"action": "back"}
        {"action": "search", "query": "..."}
        {"action": "extract"}
        {"action": "screenshot", "path": "/tmp/screen.png"}
        {"action": "quit"}
    """
    from .search import search_ddg

    # Track last dialog (alert/confirm/prompt)
    last_dialog: dict = {}

    async with StealthBrowser(headless=headless, proxy=proxy, profile=profile) as browser:
        page = await browser.new_page()

        # Auto-handle dialogs and record them
        async def _on_dialog(dialog: Dialog):
            last_dialog["type"] = dialog.type
            last_dialog["message"] = dialog.message
            await dialog.accept()

        page.on("dialog", _on_dialog)

        # Initial navigation
        if start_query:
            results = await search_ddg(start_query, max_results=5, proxy=proxy)
            _send({"status": "ok", "action": "search", "results": results})
            if results:
                await page.goto(results[0]["url"], wait_until="domcontentloaded")
                await _wait_for_content(page)
                state = await _get_page_state(page)
                _send({"status": "ok", "action": "initial_page", **state})
        elif start_url:
            await page.goto(start_url, wait_until="domcontentloaded")
            await _wait_for_content(page)
            state = await _get_page_state(page)
            _send({"status": "ok", "action": "goto", **state})
        else:
            _send({"status": "ok", "action": "ready", "message": "Browser ready. Send a command."})

        # REPL loop
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                cmd = json.loads(line)
                action = cmd.get("action", "")

                # Attach dialog info if any
                dialog_info = None
                if last_dialog:
                    dialog_info = dict(last_dialog)
                    last_dialog.clear()

                if action == "quit":
                    _send({"status": "ok", "action": "quit"})
                    break

                elif action == "goto":
                    url = cmd["url"]
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await _wait_for_content(page)
                        state = await _get_page_state(page)
                        resp = {"status": "ok", "action": "goto", **state}
                        if dialog_info:
                            resp["dialog"] = dialog_info
                        _send(resp)
                    except Exception as e:
                        _send({"status": "error", "action": "goto", "error": str(e)})

                elif action == "click":
                    index = cmd["index"]
                    try:
                        visible = await _collect_visible_clickables(page)
                        if 0 <= index < len(visible):
                            await visible[index].scroll_into_view_if_needed()
                            await StealthBrowser.human_delay(0.2, 0.5)
                            await visible[index].click()
                            await StealthBrowser.human_delay(2.0, 4.0)
                            try:
                                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                            except Exception:
                                pass
                            state = await _get_page_state(page)
                            resp = {"status": "ok", "action": "click", "clicked_index": index, **state}
                            if dialog_info:
                                resp["dialog"] = dialog_info
                            _send(resp)
                        else:
                            _send({"status": "error", "action": "click",
                                   "error": f"Index {index} out of range (0-{len(visible)-1})"})
                    except Exception as e:
                        _send({"status": "error", "action": "click", "error": str(e)})

                elif action == "hover":
                    index = cmd["index"]
                    try:
                        visible = await _collect_visible_clickables(page)
                        if 0 <= index < len(visible):
                            await visible[index].scroll_into_view_if_needed()
                            await visible[index].hover()
                            await StealthBrowser.human_delay(0.5, 1.5)
                            state = await _get_page_state(page)
                            _send({"status": "ok", "action": "hover", "hovered_index": index, **state})
                        else:
                            _send({"status": "error", "action": "hover",
                                   "error": f"Index {index} out of range (0-{len(visible)-1})"})
                    except Exception as e:
                        _send({"status": "error", "action": "hover", "error": str(e)})

                elif action == "type":
                    input_index = cmd.get("input_index", 0)
                    text = cmd["text"]
                    submit = cmd.get("submit", False)
                    clear = cmd.get("clear", True)
                    try:
                        visible_inputs = await _collect_visible_inputs(page)
                        if 0 <= input_index < len(visible_inputs):
                            el = visible_inputs[input_index]
                            await el.scroll_into_view_if_needed()
                            await el.click()
                            if clear:
                                await el.fill("")
                            await el.type(text, delay=50)
                            await StealthBrowser.human_delay(0.3, 0.8)
                            if submit:
                                await el.press("Enter")
                                await StealthBrowser.human_delay(2.0, 4.0)
                                try:
                                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                                except Exception:
                                    pass
                            state = await _get_page_state(page)
                            _send({"status": "ok", "action": "type", **state})
                        else:
                            _send({"status": "error", "action": "type",
                                   "error": f"Input index {input_index} out of range (0-{len(visible_inputs)-1})"})
                    except Exception as e:
                        _send({"status": "error", "action": "type", "error": str(e)})

                elif action == "select":
                    input_index = cmd.get("input_index", 0)
                    value = cmd.get("value")
                    label = cmd.get("label")
                    try:
                        selects = await page.query_selector_all("select")
                        visible_selects = [s for s in selects if await s.is_visible()]
                        if 0 <= input_index < len(visible_selects):
                            el = visible_selects[input_index]
                            if value is not None:
                                await el.select_option(value=value)
                            elif label is not None:
                                await el.select_option(label=label)
                            await StealthBrowser.human_delay(0.5, 1.5)
                            state = await _get_page_state(page)
                            _send({"status": "ok", "action": "select", **state})
                        else:
                            _send({"status": "error", "action": "select",
                                   "error": f"Select index {input_index} out of range (0-{len(visible_selects)-1})"})
                    except Exception as e:
                        _send({"status": "error", "action": "select", "error": str(e)})

                elif action == "press_key":
                    key = cmd["key"]
                    try:
                        await page.keyboard.press(key)
                        await StealthBrowser.human_delay(0.3, 0.8)
                        state = await _get_page_state(page)
                        _send({"status": "ok", "action": "press_key", "key": key, **state})
                    except Exception as e:
                        _send({"status": "error", "action": "press_key", "error": str(e)})

                elif action == "scroll":
                    direction = cmd.get("direction", "down")
                    pixels = cmd.get("pixels", 800)
                    if direction == "up":
                        pixels = -pixels
                    await page.evaluate(f"window.scrollBy(0, {pixels})")
                    await StealthBrowser.human_delay(0.5, 1.5)
                    state = await _get_page_state(page)
                    _send({"status": "ok", "action": "scroll", **state})

                elif action == "wait":
                    ms = cmd.get("ms", 2000)
                    ms = min(ms, 30000)
                    await asyncio.sleep(ms / 1000)
                    state = await _get_page_state(page)
                    _send({"status": "ok", "action": "wait", **state})

                elif action == "wait_for":
                    text = cmd.get("text")
                    selector = cmd.get("selector")
                    timeout = min(cmd.get("timeout", 10000), 30000)
                    try:
                        if text:
                            await page.wait_for_function(
                                f"() => document.body.innerText.includes('{text}')",
                                timeout=timeout,
                            )
                        elif selector:
                            await page.wait_for_selector(selector, timeout=timeout)
                        state = await _get_page_state(page)
                        _send({"status": "ok", "action": "wait_for", **state})
                    except Exception as e:
                        state = await _get_page_state(page)
                        _send({"status": "timeout", "action": "wait_for", "error": str(e), **state})

                elif action == "back":
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    await StealthBrowser.human_delay(1.5, 3.0)
                    state = await _get_page_state(page)
                    _send({"status": "ok", "action": "back", **state})

                elif action == "forward":
                    try:
                        await page.go_forward(wait_until="domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    await StealthBrowser.human_delay(1.5, 3.0)
                    state = await _get_page_state(page)
                    _send({"status": "ok", "action": "forward", **state})

                elif action == "search":
                    query = cmd["query"]
                    results = await search_ddg(
                        query, max_results=cmd.get("max_results", 5), proxy=proxy
                    )
                    _send({"status": "ok", "action": "search", "results": results})

                elif action == "extract":
                    state = await _get_page_state(page)
                    _send({"status": "ok", "action": "extract", **state})

                elif action == "screenshot":
                    path = cmd.get("path", "/tmp/scrapper_screenshot.png")
                    await page.screenshot(path=path, full_page=cmd.get("full_page", False))
                    _send({"status": "ok", "action": "screenshot", "path": path})

                elif action == "eval_js":
                    # Run arbitrary JS and return result
                    expression = cmd["expression"]
                    try:
                        result = await page.evaluate(expression)
                        _send({"status": "ok", "action": "eval_js", "result": result})
                    except Exception as e:
                        _send({"status": "error", "action": "eval_js", "error": str(e)})

                else:
                    _send({"status": "error", "error": f"Unknown action: {action}"})

            except json.JSONDecodeError as e:
                _send({"status": "error", "error": f"Invalid JSON: {e}"})
            except KeyboardInterrupt:
                break
            except Exception as e:
                _send({"status": "error", "error": str(e)})

        await page.close()


def _send(data: dict):
    """Write a JSON line to stdout and flush."""
    json.dump(data, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()
