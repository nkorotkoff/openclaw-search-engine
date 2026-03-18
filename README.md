# Scrapper Engine

Stealth web scraper and browser automation tool for OpenClaw. Navigates any website — including heavily protected ones like Ozon, Wildberries, and other sites with aggressive antibot systems — extracts content, and returns structured JSON.

Built on [Camoufox](https://github.com/daijro/camoufox), a modified Firefox with patches for canvas, WebGL, fonts, navigator, and other fingerprinting vectors.

## Installation

```bash
git clone <repo-url>
cd scrapperEngine
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Download the Camoufox browser binary (~700 MB)
python -m camoufox fetch
```

## Two Modes of Operation

### 1. `search` — Search & Scrape

Searches DuckDuckGo, visits the top result pages, extracts content. One-shot mode — run, get JSON, done.

```bash
scrapper search "tablet under $200 10 inch" --pretty
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `-n, --max-results` | 5 | Number of search results to fetch from DDG |
| `-p, --max-pages` | 3 | Number of result pages to actually visit and scrape |
| `--follow-links` | off | Also follow and scrape links found on visited pages |
| `--proxy` | — | Proxy server (`http://user:pass@host:port`) |
| `--profile` | — | Browser profile name (persists cookies between runs) |
| `--no-headless` | off | Show browser window (for debugging) |
| `--pretty` | off | Pretty-print JSON output |

**Output format:**

```json
{
  "query": "tablet under $200 10 inch",
  "search_results": [
    {
      "title": "Best Budget Tablets - Ozon",
      "url": "https://www.ozon.ru/category/planshety-...",
      "snippet": "Tablets 10 inch under 10000 rubles at OZON..."
    }
  ],
  "pages": [
    {
      "url": "https://www.ozon.ru/category/planshety-...",
      "title": "Buy Tablets at OZON",
      "text": "...extracted page text (up to 15000 characters)...",
      "links": [
        {"text": "BORVI Tablet 10.1\"", "url": "https://www.ozon.ru/product/..."}
      ]
    }
  ]
}
```

### 2. `interact` — Interactive Browser Session

A REPL-style browser session designed for LLMs. The model sends JSON commands via stdin and receives responses with indexed clickable elements, input fields, and page text on stdout. Enables complex multi-step workflows: buying train tickets, filling forms, navigating e-commerce sites, etc.

```bash
scrapper interact --query "headphones under $50"
scrapper interact --url "https://www.tutu.ru/poezda/"
```

**Options:**

| Flag | Description |
|------|-------------|
| `--url` | Navigate to this URL on start |
| `-q, --query` | Start with a DDG search |
| `--proxy` | Proxy server |
| `--profile` | Browser profile name |
| `--no-headless` | Show browser window |

**Commands:**

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Search DuckDuckGo | `{"action": "search", "query": "..."}` |
| `goto` | Navigate to URL | `{"action": "goto", "url": "https://..."}` |
| `click` | Click an element by index | `{"action": "click", "index": 15}` |
| `hover` | Hover over element (dropdowns, menus) | `{"action": "hover", "index": 5}` |
| `type` | Type text into an input field | `{"action": "type", "input_index": 0, "text": "Moscow", "submit": true}` |
| `select` | Choose an option from `<select>` | `{"action": "select", "input_index": 2, "value": "economy"}` |
| `press_key` | Press a keyboard key | `{"action": "press_key", "key": "Tab"}` |
| `scroll` | Scroll the page | `{"action": "scroll", "direction": "down", "pixels": 800}` |
| `wait` | Wait N milliseconds | `{"action": "wait", "ms": 3000}` |
| `wait_for` | Wait for text or selector to appear | `{"action": "wait_for", "text": "Results found"}` |
| `back` | Navigate back | `{"action": "back"}` |
| `forward` | Navigate forward | `{"action": "forward"}` |
| `extract` | Re-extract current page state | `{"action": "extract"}` |
| `screenshot` | Save a screenshot | `{"action": "screenshot", "path": "/tmp/s.png"}` |
| `eval_js` | Execute JavaScript on the page | `{"action": "eval_js", "expression": "document.title"}` |
| `quit` | Close the session | `{"action": "quit"}` |

**`type` options:**

| Field | Default | Description |
|-------|---------|-------------|
| `input_index` | 0 | Which input field to type into |
| `text` | required | Text to type |
| `submit` | false | Press Enter after typing |
| `clear` | true | Clear the field before typing |

**Response format:**

Each response is a single JSON line on stdout:

```json
{
  "status": "ok",
  "action": "goto",
  "url": "https://www.tutu.ru/poezda/",
  "title": "Train tickets — Tutu.ru",
  "text": "...page text...",
  "elements": [
    {"index": 0, "type": "link", "text": "Войти", "href": "/login"},
    {"index": 5, "type": "button", "text": "Найти"},
    {"index": 12, "type": "role-button", "text": "Эконом"},
    {"index": 18, "type": "tab", "text": "Туда и обратно"}
  ],
  "inputs": [
    {"index": 0, "type": "input", "name": "from", "placeholder": "From", "label": "from", "value": ""},
    {"index": 1, "type": "input", "name": "to", "placeholder": "To", "label": "to", "value": ""},
    {"index": 2, "type": "text", "name": "", "placeholder": "Date", "label": "Date", "value": ""},
    {"index": 3, "type": "select", "name": "class", "placeholder": "", "label": "class", "value": "economy",
     "options": [
       {"value": "economy", "text": "Economy", "selected": true},
       {"value": "business", "text": "Business", "selected": false}
     ]}
  ],
  "dialog": {"type": "alert", "message": "Session expired"}
}
```

**Element types:**

| Type | What it is |
|------|-----------|
| `link` | `<a>` tag with href |
| `button` | `<button>` or `<input type="submit">` |
| `role-button` | `<div role="button">` and similar custom elements |
| `tab` | `<div role="tab">` — tab switchers |
| `menuitem` | `<div role="menuitem">` — dropdown menu items |

**Input types:**

| Type | What it is |
|------|-----------|
| `input` / `text` / `email` / `password` / `tel` / `number` | Text input fields |
| `textarea` | Multi-line text |
| `select` | Dropdown with `options[]` listing available choices |

## Integration with OpenClaw

### search — One-shot call

```python
import subprocess, json

result = subprocess.run(
    ["scrapper", "search", "tablet under $200", "-p", "2"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
```

### interact — Stateful browsing session

```python
import subprocess, json

proc = subprocess.Popen(
    ["scrapper", "interact"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL, text=True, bufsize=1
)

def send(cmd: dict) -> dict:
    proc.stdin.write(json.dumps(cmd) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

# Read the initial "ready" message
proc.stdout.readline()

# Search
results = send({"action": "search", "query": "headphones under $50"})

# Navigate to the first result
page = send({"action": "goto", "url": results["results"][0]["url"]})

# The model sees elements and decides what to click
page = send({"action": "click", "index": 15})

# Type into a search field on the page
page = send({"action": "type", "input_index": 0, "text": "TWS", "submit": True})

# Done
send({"action": "quit"})
proc.wait()
```

### Example: buying a train ticket

```python
# Navigate to tutu.ru
page = send({"action": "goto", "url": "https://www.tutu.ru/poezda/"})
# page["inputs"] shows:
#   [0] placeholder="From"
#   [1] placeholder="To"
#   [2] placeholder="Date"

# Fill in the route
page = send({"action": "type", "input_index": 0, "text": "Moscow"})
page = send({"action": "wait", "ms": 1000})       # wait for autocomplete
page = send({"action": "press_key", "key": "Enter"})  # select suggestion

page = send({"action": "type", "input_index": 1, "text": "St. Petersburg"})
page = send({"action": "wait", "ms": 1000})
page = send({"action": "press_key", "key": "Enter"})

# Set date
page = send({"action": "type", "input_index": 2, "text": "25.04.2026"})

# Click "Search"
# Find the search button in page["elements"]
search_btn = next(e for e in page["elements"] if "Найти" in e["text"])
page = send({"action": "click", "index": search_btn["index"]})

# Wait for results
page = send({"action": "wait_for", "text": "поездов найдено"})

# Now page["elements"] contains train options — click one
page = send({"action": "click", "index": 3})

# Continue: select seat, fill passenger info, etc.
```

## Anti-Detection

- **Camoufox** — modified Firefox that patches canvas, WebGL, fonts, AudioContext, navigator.webdriver, and other fingerprinting vectors
- **Humanize** — randomized delays between actions, simulating human behavior at the browser engine level
- **Persistent profiles** — cookies and sessions survive between runs (`--profile myprofile`)
- **uBlock Origin** — built-in by default, blocks trackers and ads
- **DDG HTML search** — lightweight POST request without a browser, avoids bot detection
- **Auto-dialog handling** — browser alerts/confirms are auto-accepted and reported in response

## Project Structure

```
scrapper/
├── __init__.py
├── browser.py       — StealthBrowser (Camoufox + persistent profiles)
├── search.py        — DuckDuckGo HTML search (httpx, no browser)
├── extractor.py     — Page content extraction (BeautifulSoup)
├── engine.py        — Search pipeline: search → scrape → JSON
├── interactive.py   — Interactive REPL session for LLMs
└── cli.py           — CLI entry point (click)
```
