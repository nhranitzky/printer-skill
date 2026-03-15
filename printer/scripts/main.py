#!/usr/bin/env python3
"""
main.py
-------
Printer Skill CLI dispatcher.

Registers all subcommands under a single Click group invoked via the
bin/printit launcher.
"""

from pathlib import Path

import click

_SKILL_ROOT  = Path(__file__).parent.parent.resolve()
_DOTENV_PATH = _SKILL_ROOT / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_DOTENV_PATH)
except ImportError:
    pass

from list_printers import list_printers_cmd  # noqa: E402
from print_file import print_file_cmd        # noqa: E402
from print_url import print_url_cmd          # noqa: E402
from print_text import print_text_cmd        # noqa: E402


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Printer skill - manage and interact with CUPS printers via the command line."""


cli.add_command(list_printers_cmd, "list")
cli.add_command(print_file_cmd,    "file")
cli.add_command(print_url_cmd,     "page")
cli.add_command(print_text_cmd,    "text")


if __name__ == "__main__":
    cli(prog_name="printer")
