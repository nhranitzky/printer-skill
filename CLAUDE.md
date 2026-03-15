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

# Run via the launcher
cd printer && bin/printit list-printers
cd printer && bin/printit print-file --file /path/to/file.pdf
cd printer && bin/printit print-url --url https://example.com
cd printer && bin/printit print-text --file /path/to/file.txt

# Run main.py directly (for development)
cd printer && uv run python scripts/main.py --help
```

## Architecture

`bin/printit` delegates to `scripts/main.py`, a Click CLI group that dispatches to four subcommands:

```
bin/printit <command> [args...]
```

The launcher runs `uv run --project <skill_root> scripts/main.py "$@"`.
Each subcommand is defined in its own module and registered in `main.py`.

### Scripts

| Script | Purpose |
|--------|---------|
| `list_printers.py` | Discovers CUPS printers; `--verbose` shows all attributes |
| `print_file.py` | Submits local files to CUPS (PDF, images, etc.) |
| `print_url.py` | Renders a URL via headless Chromium (Playwright) → prints |
| `print_text.py` | Converts a text file to PDF via ReportLab → prints |

### Dependencies

- `click` — CLI framework (group + subcommand dispatch)
- `pycups` — CUPS bindings (requires CUPS running: `lpstat -r`)
- `playwright` — headless Chromium for URL printing (first run: `playwright install chromium`)
- `reportlab` — PDF generation for text printing
- `python-dotenv` — `.env` loading

## Key conventions

- Python ≥ 3.13 required (`pyproject.toml`)
- `archiv/` contains legacy scripts — do not modify or reference them
- No test framework is configured
- The `SKILL.md` file must not use colons (`:`) in the `description` field
