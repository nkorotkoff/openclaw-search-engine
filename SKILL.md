# Skill: Web Browser

You have access to a stealth web browser that can navigate any website, including heavily protected ones (Ozon, Wildberries, etc.). Use it to search the web, browse pages, fill forms, click buttons, and complete multi-step tasks like purchasing items or booking tickets.

## How It Works

You communicate with the browser by sending JSON commands to `scrapper` via stdin. Each command returns a JSON response with the current page state: text content, clickable elements (indexed), and input fields (indexed).

You see the page as structured data — not pixels. Use element and input indices to interact.

## Quick Start

### One-shot search (no interaction needed)

```bash
scrapper search "wireless headphones under $50" --pretty -p 3
```

Returns search results + scraped page content as JSON.

### Interactive session (multi-step tasks)

```bash
scrapper interact --url "https://www.ozon.ru"
```

Then send JSON commands via stdin, one per line.

## Commands Reference

### Navigation

```jsonl
{"action": "search", "query": "best laptop under $500"}
{"action": "goto", "url": "https://example.com"}
{"action": "back"}
{"action": "forward"}
{"action": "scroll", "direction": "down", "pixels": 800}
{"action": "scroll", "direction": "up"}
```

### Clicking

```jsonl
{"action": "click", "index": 15}
{"action": "hover", "index": 5}
```

`index` refers to the element index from the `elements` array in the response.

### Typing

```jsonl
{"action": "type", "input_index": 0, "text": "Moscow"}
{"action": "type", "input_index": 1, "text": "query", "submit": true}
{"action": "type", "input_index": 0, "text": "append this", "clear": false}
```

`input_index` refers to the input index from the `inputs` array in the response.

- `submit: true` — press Enter after typing
- `clear: false` — don't erase existing value before typing

### Dropdowns

```jsonl
{"action": "select", "input_index": 2, "value": "economy"}
{"action": "select", "input_index": 2, "label": "Business class"}
```

Use `value` or `label` to pick an option. Available options are listed in the input's `options` array.

### Keyboard

```jsonl
{"action": "press_key", "key": "Tab"}
{"action": "press_key", "key": "Escape"}
{"action": "press_key", "key": "ArrowDown"}
{"action": "press_key", "key": "Enter"}
```

### Waiting

```jsonl
{"action": "wait", "ms": 2000}
{"action": "wait_for", "text": "Results found"}
{"action": "wait_for", "selector": ".search-results", "timeout": 10000}
```

Use `wait` after actions that trigger animations or AJAX loading.
Use `wait_for` when you expect specific content to appear.

### Utility

```jsonl
{"action": "extract"}
{"action": "screenshot", "path": "/tmp/debug.png"}
{"action": "eval_js", "expression": "document.querySelectorAll('.price').length"}
{"action": "quit"}
```

## Response Format

Every command returns a JSON line:

```json
{
  "status": "ok",
  "action": "goto",
  "url": "https://www.tutu.ru/poezda/",
  "title": "Train tickets",
  "text": "Full page text content...",
  "elements": [
    {"index": 0, "type": "link", "text": "Login", "href": "/login"},
    {"index": 5, "type": "button", "text": "Search"},
    {"index": 8, "type": "role-button", "text": "Economy"}
  ],
  "inputs": [
    {"index": 0, "type": "input", "name": "from", "placeholder": "From", "label": "from", "value": ""},
    {"index": 1, "type": "select", "name": "class", "label": "class", "value": "economy",
     "options": [{"value": "economy", "text": "Economy", "selected": true}]}
  ]
}
```

### What you get

- **`text`** — readable page content (up to 15000 chars). Use this to understand what's on the page.
- **`elements`** — clickable things: links, buttons, tabs, menu items. Each has an `index` you pass to `click` or `hover`.
- **`inputs`** — form fields: text inputs, textareas, selects. Each has an `index` you pass to `type` or `select`.
- **`dialog`** — if a browser alert/confirm appeared, its message is here. Dialogs are auto-accepted.
- **`status`** — `"ok"`, `"error"`, or `"timeout"`.

## Patterns & Tips

### Autocomplete fields (cities, addresses)

Many sites show suggestions as you type. The pattern is:

1. `type` the text into the field
2. `wait` 1-2 seconds for suggestions to load
3. `extract` to see the suggestion list in elements
4. `click` the correct suggestion, or `press_key: "Enter"` to accept the first one

### Date pickers

Date pickers are usually custom widgets. Try:

1. `click` the date input to open the picker
2. `extract` to see the calendar in elements
3. `click` the desired date

Or if the field accepts text: `type` the date directly (e.g. `"25.04.2026"`).

### Pagination / "Load more"

1. `scroll` down to trigger lazy loading
2. `extract` to get updated content
3. Or `click` the "Next page" / "Load more" button from elements

### Forms with multiple steps

1. Fill visible fields with `type`
2. `click` "Next" / "Continue"
3. `wait_for` the next step to load
4. Repeat

### Handling errors

If `status` is `"error"`, read the `error` field and adjust. Common issues:
- Index out of range — the page changed, `extract` first to get fresh indices
- Timeout — the page is slow, try `wait` then `extract`
- Navigation failed — URL might be wrong, try `search` instead

### When you don't know the URL

Use `search` to find it:

```jsonl
{"action": "search", "query": "buy train tickets Moscow to St Petersburg"}
```

Then `goto` the most relevant result URL.

## Limitations

- No file upload support
- Payment iframes (card entry) may require `eval_js` to interact with
- CAPTCHAs cannot be solved automatically
- Maximum text output is 15000 characters per page (truncated)
- Maximum 150 elements and 30 inputs per response
