#!/usr/bin/env python3
"""
print_file.py
-------------
Send a file to a CUPS printer with configurable options such as duplex
(double-sided) printing, number of copies, and explicit printer selection.

The script reads default settings from a `.env` file in the same directory.
Command-line arguments always override .env defaults.

Usage:
    python print_file.py --file /path/to/document.pdf
    python print_file.py --file report.pdf --printer "HP_LaserJet"
    python print_file.py --file report.pdf --duplex
    python print_file.py --file report.pdf --simplex
    python print_file.py --file report.pdf --printer "Epson_WF" --duplex --copies 3
    python print_file.py --help

Environment variables (via .env file in the script directory):
    DEFAULT_PRINTER   Name of the CUPS printer to use when --printer is not given.
    DEFAULT_DUPLEX    "true" or "false" – whether to default to duplex printing.

Requirements:
    pip install pycups python-dotenv
"""

import argparse
import os
import sys
from pathlib import Path

# ── Load .env from the script's own directory ─────────────────────────────────
_SKILL_ROOT  = Path(__file__).parent.parent.resolve()
_DOTENV_PATH = _SKILL_ROOT / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_DOTENV_PATH)
except ImportError:
    print(
        "Warning: 'python-dotenv' is not installed. .env file will be ignored.\n"
        "Install with: pip install python-dotenv",
        file=sys.stderr,
    )

try:
    import cups
except ImportError:
    print("Error: 'pycups' is not installed. Run: pip install pycups", file=sys.stderr)
    sys.exit(1)

from utils import _str_to_bool, get_cups_connection, resolve_printer, build_print_options  # noqa: E402


def print_file(
    file_path: str,
    printer_name: str | None = None,
    duplex: bool | None = None,
    copies: int = 1,
    title: str | None = None,
    media: str | None = None,
    orientation: str | None = None,
) -> None:
    """
    Submit a print job to CUPS.

    Args:
        file_path:    Absolute or relative path to the file to print.
        printer_name: CUPS printer name. If None, resolved via .env / CUPS default.
        duplex:       True = duplex, False = simplex, None = use DEFAULT_DUPLEX from .env.
        copies:       Number of copies (default: 1).
        title:        Optional job title shown in the CUPS queue. Defaults to filename.
        media:        Optional paper size (e.g. "A4", "Letter").
        orientation:  Optional "portrait" or "landscape".
    """
    # Resolve file path
    resolved_path = Path(file_path).resolve()
    if not resolved_path.exists():
        print(f"Error: File not found: {resolved_path}", file=sys.stderr)
        sys.exit(1)
    if not resolved_path.is_file():
        print(f"Error: Path is not a file: {resolved_path}", file=sys.stderr)
        sys.exit(1)

    # Resolve duplex setting
    if duplex is None:
        env_duplex = os.getenv("DEFAULT_DUPLEX", "false").strip()
        duplex = _str_to_bool(env_duplex)

    # Connect to CUPS
    conn = get_cups_connection()

    # Resolve printer
    resolved_printer = resolve_printer(conn, printer_name)

    # Build options
    options = build_print_options(
        duplex=duplex,
        copies=copies,
        media=media,
        orientation=orientation,
    )

    # Job title
    job_title = title or resolved_path.name

    # Submit the job
    print(f"\nSubmitting print job:")
    print(f"  File    : {resolved_path}")
    print(f"  Printer : {resolved_printer}")
    print(f"  Sides   : {'duplex (two-sided)' if duplex else 'simplex (one-sided)'}")
    print(f"  Copies  : {copies}")
    if media:
        print(f"  Media   : {media}")
    if orientation:
        print(f"  Orient. : {orientation}")
    print(f"  Title   : {job_title}")
    print()

    try:
        job_id = conn.printFile(
            printer=resolved_printer,
            filename=str(resolved_path),
            title=job_title,
            options=options,
        )
        print(f"✓ Print job submitted successfully.")
        print(f"  Job ID  : {job_id}")
        print(f"  Monitor : lpstat -o {resolved_printer}")
        print(f"  Cancel  : cancel {job_id}\n")
    except cups.IPPError as exc:
        err_code, err_msg = exc.args
        print(f"Error: CUPS rejected the print job.", file=sys.stderr)
        print(f"  Code   : {err_code}", file=sys.stderr)
        print(f"  Message: {err_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error while printing: {exc}", file=sys.stderr)
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # Read environment defaults for help text
    env_printer = os.getenv("DEFAULT_PRINTER", "not set")
    env_duplex  = os.getenv("DEFAULT_DUPLEX",  "false")

    parser = argparse.ArgumentParser(
        description="Print a file via CUPS with configurable options.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Current .env defaults (from {_DOTENV_PATH}):\n"
            f"  DEFAULT_PRINTER = {env_printer}\n"
            f"  DEFAULT_DUPLEX  = {env_duplex}\n\n"
            "Examples:\n"
            "  python print_file.py --file report.pdf\n"
            "  python print_file.py --file report.pdf --duplex\n"
            "  python print_file.py --file report.pdf --printer HP_LaserJet --copies 2\n"
        ),
    )

    parser.add_argument(
        "--file", "-f",
        required=True,
        metavar="PATH",
        help="Path to the file to print (e.g. /home/user/report.pdf).",
    )
    parser.add_argument(
        "--printer", "-p",
        default=None,
        metavar="NAME",
        help=(
            "CUPS printer name to use. Overrides DEFAULT_PRINTER from .env. "
            "Run list_printers.py to see available names."
        ),
    )

    # Mutually exclusive duplex / simplex flags
    sides_group = parser.add_mutually_exclusive_group()
    sides_group.add_argument(
        "--duplex", "-d",
        action="store_true",
        default=None,
        help="Print two-sided (duplex, long-edge binding).",
    )
    sides_group.add_argument(
        "--simplex", "-s",
        action="store_true",
        default=None,
        help="Print one-sided (simplex). Overrides DEFAULT_DUPLEX=true in .env.",
    )

    parser.add_argument(
        "--copies", "-n",
        type=int,
        default=1,
        metavar="N",
        help="Number of copies to print (default: 1).",
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        metavar="TITLE",
        help="Job title shown in the CUPS queue (default: filename).",
    )
    parser.add_argument(
        "--media", "-m",
        default=None,
        metavar="SIZE",
        help='Paper size, e.g. "A4" or "Letter" (default: printer default).',
    )
    parser.add_argument(
        "--orientation", "-o",
        choices=["portrait", "landscape"],
        default=None,
        help="Page orientation (default: printer default).",
    )

    args = parser.parse_args()

    # Resolve duplex flag: --simplex forces False, --duplex forces True, else None→.env
    if args.simplex:
        duplex_value: bool | None = False
    elif args.duplex:
        duplex_value = True
    else:
        duplex_value = None  # will be resolved from .env inside print_file()

    if args.copies < 1:
        print("Error: --copies must be at least 1.", file=sys.stderr)
        sys.exit(1)

    print_file(
        file_path=args.file,
        printer_name=args.printer,
        duplex=duplex_value,
        copies=args.copies,
        title=args.title,
        media=args.media,
        orientation=args.orientation,
    )


if __name__ == "__main__":
    main()
