# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
make install          # runs: cd printer && uv sync

# Lint
make lint             # runs: uv run ruff check printer/scripts

# Package
make package          # builds: printer.skill_v1.0.zip

# Deploy to Openclaw device
make deploy           # scp zip to ${TARGET}:/home/pi/downloads

# Run a script directly
cd printer && uv run python scripts/list_printers.py
cd printer && uv run python scripts/print_file.py --file /path/to/file.pdf
cd printer && uv run python scripts/print_url.py --url https://example.com
cd printer && uv run python scripts/print_text.py --file /path/to/file.txt
```

## Architecture

The skill has no `main.py` CLI group — instead, each script is a standalone argparse program invoked independently via the `bin/printit` bash launcher:

```
bin/printit <script_name> [args...]
```

The launcher resolves the script name from `scripts/`, then delegates to `uv run --project <skill_root> python scripts/<script_name>.py`.

### Scripts

| Script | Purpose |
|--------|---------|
| `list_printers.py` | Discovers CUPS printers; `--verbose` shows all attributes |
| `print_file.py` | Submits local files to CUPS (PDF, images, etc.) |
| `print_url.py` | Renders a URL via headless Chromium (Playwright) → prints |
| `print_text.py` | Converts a text file to PDF via ReportLab → prints |

### Dependencies

- `pycups` — CUPS bindings (requires CUPS running: `lpstat -r`)
- `playwright` — headless Chromium for URL printing (first run: `playwright install chromium`)
- `reportlab` — PDF generation for text printing
- `python-dotenv` — `.env` loading

## Key conventions

- Python ≥ 3.13 required (`pyproject.toml`)
- `archiv/` contains legacy scripts — do not modify or reference them
- No test framework is configured
- The `SKILL.md` file must not use colons (`:`) in the `description` field
