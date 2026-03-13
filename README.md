# Printer Skill

Print files, web pages, and text to any CUPS printer from the command line.

## Setup

### CLI

```bash
cd printer
uv sync
uv run playwright install chromium
chmod +x bin/printit
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and CUPS installed and running (`lpstat -r` to verify).

### Openclaw / Claude Code

See [printer/setup/SETUP.md](printer/setup/SETUP.md).

---

## CLI Usage

All commands are invoked via `bin/printit`:

```bash
bin/printit <script> [options]
```

### List printers

```bash
# JSON output (default)
bin/printit list_printers
bin/printit list_printers --json

# Human-readable text table
bin/printit list_printers --text
bin/printit list_printers --text --verbose
```

**JSON output format:**

```json
{
  "total": 2,
  "default_printer": "HP_LaserJet",
  "printers": [
    {
      "name": "HP_LaserJet",
      "uri": "ipp://192.168.1.10:631/printers/HP_LaserJet",
      "state": "idle",
      "is_default": true
    },
    {
      "name": "Epson_WF",
      "uri": "ipp://192.168.1.20:631/printers/Epson_WF",
      "state": "stopped",
      "is_default": false
    }
  ]
}
```

With `--verbose`, each printer entry also includes an `"attributes"` object containing all raw CUPS PPD attributes.

### Print a file

```bash
bin/printit print_file --file /path/to/document.pdf
bin/printit print_file --file report.pdf --printer "HP_LaserJet"
bin/printit print_file --file report.pdf --duplex
bin/printit print_file --file report.pdf --copies 2 --media A4
```

| Option | Description |
|---|---|
| `--file` | Path to file (required) |
| `--printer` | CUPS printer name (auto-selected if only one exists) |
| `--duplex` / `--simplex` | Two-sided or one-sided |
| `--copies N` | Number of copies (default: 1) |
| `--media SIZE` | Paper size: A4, Letter, Legal, … |
| `--orientation` | portrait or landscape |
| `--title` | Job title in the CUPS queue |

### Print a URL

```bash
bin/printit print_url --url https://example.com
bin/printit print_url --url https://example.com --scale 0.8 --landscape
bin/printit print_url --url https://example.com --wait 3
bin/printit print_url --url https://dashboard.example.com --no-network-wait
```

| Option | Description |
|---|---|
| `--url` | Web page to print (required) |
| `--scale FACTOR` | CSS scale 0.1–2.0; use 0.8 for wide pages (default: 1.0) |
| `--landscape` | Landscape orientation |
| `--wait SECONDS` | Extra delay for animations or lazy-loaded content |
| `--no-network-wait` | Skip network-idle wait for live/streaming pages |
| `--viewport-width PX` | Browser window width (default: 1280) |
| `--media SIZE` | Paper size (default: A4) |
| `--printer` | CUPS printer name (auto-selected if only one exists) |
| `--duplex` / `--simplex` | Two-sided or one-sided |
| `--copies N` | Number of copies |

### Print a text file

```bash
bin/printit print_text --file notes.txt
bin/printit print_text --file notes.txt --font Helvetica --font-size 11
bin/printit print_text --file output.log --font Courier --font-size 8 --landscape
bin/printit print_text --file report.txt --font Times-Roman --duplex
```

| Option | Description |
|---|---|
| `--file` | Path to text file (required) |
| `--font NAME` | Courier, Helvetica, Times-Roman (and Bold/Italic variants) |
| `--font-size PT` | Font size in points (default: 10) |
| `--line-spacing` | Line height multiplier (default: 1.2) |
| `--margin VALUE` | Page margin: 2cm, 15mm, 72pt (default: 2cm) |
| `--landscape` | Landscape orientation |
| `--media SIZE` | Paper size (default: A4) |
| `--encoding ENC` | File encoding (default: utf-8) |
| `--printer` | CUPS printer name (auto-selected if only one exists) |
| `--duplex` / `--simplex` | Two-sided or one-sided |
| `--copies N` | Number of copies |

---

## License

MIT

---

## Implementation Explanation



### Overall Architecture

```
User
  │
  ▼
bin/printit  ← front desk (bash launcher)
  │
  ├──► scripts/list_printers.py   ← "What printers do you have?"
  ├──► scripts/print_file.py      ← "Print this PDF/image"
  ├──► scripts/print_url.py       ← "Print this website"
  └──► scripts/print_text.py      ← "Print this .txt file"
            │
            ▼
       scripts/utils.py           ← shared helpers (CUPS connection,
            │                        printer resolution, options builder)
            ▼
          CUPS                    ← OS print spooler → physical printer
```

---

### The Launcher: `bin/printit`

This bash script is the **only entry point**. It does three things:

```
printit list_printers --verbose
   │
   ├─ [1] Resolves SKILL_ROOT (one level above bin/)
   ├─ [2] Validates the script name, appends .py if missing
   ├─ [3] Checks 'uv' is on PATH
   └─ [4] exec uv run --project SKILL_ROOT  scripts/<name>.py  [args...]
```

The `exec` at the end **replaces** the bash process with `uv run` — no parent bash process lingers. `set -euo pipefail` means any error aborts immediately.

---

### Shared Logic: `utils.py`

All four scripts share three helpers:

**`get_cups_connection()`** — connects to the local CUPS daemon or exits cleanly.

**`resolve_printer()`** — a priority waterfall:
```
--printer flag  →  DEFAULT_PRINTER in .env  →  CUPS system default  →  first alphabetically
```

**`build_print_options()`** — translates human flags (`duplex=True`, `copies=3`) into the raw CUPS IPP dictionary CUPS expects:
```python
{"sides": "two-sided-long-edge", "copies": "3", "orientation-requested": "4"}
```

---

### The Four Scripts

**`list_printers.py`**
Queries `conn.getPrinters()` and renders a fixed-width ASCII table. `--verbose` dumps every raw CUPS attribute (useful for debugging PPD settings).

**`print_file.py`**
The simplest path:
```
resolve file path → resolve printer → build options → conn.printFile()
```
Duplex defaults come from `.env`'s `DEFAULT_DUPLEX`. `--simplex` and `--duplex` are **mutually exclusive** via argparse.

**`print_url.py`**
The most complex path:
```
URL  →  headless Chromium (Playwright)  →  temp PDF  →  conn.printFile()  →  cleanup
```
The `render_url_to_pdf()` function launches Chromium inside a `with sync_playwright()` context, navigates, waits for `networkidle`, then calls `page.pdf()`. The temp file is always cleaned up in a `finally` block — even if printing fails.

**`print_text.py`**
```
.txt file  →  ReportLab canvas  →  temp PDF  →  conn.printFile()  →  cleanup
```
`text_to_pdf()` manually lays out text line by line, tracking a `y` cursor. When `y` drops below the bottom margin it calls `new_page()`. Long lines are word-wrapped using `pdfmetrics.stringWidth()` to measure actual pixel widths rather than character counts.

---

### Gotcha: The Duplex `None` Three-State

`duplex` is intentionally `bool | None` throughout, not just `bool`. The three states mean:

| Value | Meaning |
|-------|---------|
| `True` | `--duplex` flag was passed |
| `False` | `--simplex` flag was passed |
| `None` | neither flag — fall through to `.env` default |

If you collapse this to a plain bool at the CLI boundary, you lose the ability to distinguish "user said simplex" from "user said nothing" — and the `.env` default would never apply. This pattern repeats identically in all three print scripts.
