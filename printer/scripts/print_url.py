#!/usr/bin/env python3
"""
print_url.py
------------
Renders a web page using a real Chromium browser (via Playwright) and prints
it via CUPS. JavaScript, CSS animations, and dynamic content are all fully
rendered before the PDF is generated.

The script performs three steps:
    1. Launch headless Chromium via Playwright
    2. Navigate to the URL, wait for the page to fully load, render to PDF
    3. Submit the PDF to CUPS (same logic as print_file.py)

The .env file in the script directory can define a default printer and
default duplex setting (see .env.example).

Usage:
    python print_url.py --url https://example.com
    python print_url.py --url https://example.com --duplex
    python print_url.py --url https://example.com --printer "HP_LaserJet"
    python print_url.py --url https://example.com --media A4 --landscape
    python print_url.py --url https://example.com --wait 5 --scale 0.8
    python print_url.py --help

First-time setup:
    pip install pycups python-dotenv playwright
    playwright install chromium

Requirements:
    - pycups        (Python CUPS bindings)
    - python-dotenv (read .env configuration)
    - playwright    (headless Chromium automation)
    - CUPS must be installed and running on the system
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

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

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print(
        "Error: 'playwright' is not installed.\n"
        "Install with: pip install playwright && playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)

from utils import _str_to_bool, get_cups_connection, resolve_printer, build_print_options  # noqa: E402


def validate_url(url: str) -> str:
    """
    Ensure the URL has a scheme. Prepends 'https://' if missing.

    Args:
        url: Raw URL string from the CLI.

    Returns:
        URL string guaranteed to have a scheme.
    """
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        print(f"Note: No scheme provided, assuming https: {url}")
    return url


# ── Core functions ────────────────────────────────────────────────────────────

def render_url_to_pdf(
    url: str,
    output_path: str,
    landscape: bool = False,
    media: str = "A4",
    scale: float = 1.0,
    wait_seconds: float = 0.0,
    wait_for_network: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 900,
) -> None:
    """
    Launch headless Chromium, navigate to the URL, and save the page as PDF.

    Args:
        url:              The web page URL to render.
        output_path:      File path where the PDF will be saved.
        landscape:        True = landscape orientation, False = portrait.
        media:            Paper format string, e.g. "A4" or "Letter".
                          Playwright accepts standard paper sizes.
        scale:            CSS scale factor (0.1 – 2.0). Useful to fit
                          wide pages onto paper (e.g. 0.8).
        wait_seconds:     Extra seconds to wait after page load before
                          capturing. Useful for pages with delayed animations.
        wait_for_network: If True, waits until all network activity settles
                          ('networkidle') before rendering. Set False for
                          pages that never fully settle (e.g. live dashboards).
        viewport_width:   Browser window width in pixels (default 1280).
        viewport_height:  Browser window height in pixels (default 900).

    Raises:
        SystemExit: On browser launch failure or navigation timeout.
    """
    print(f"  Launching headless Chromium…")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
        )
        page = context.new_page()

        # Determine wait condition
        wait_until = "networkidle" if wait_for_network else "domcontentloaded"

        print(f"  Navigating to: {url}")
        try:
            page.goto(url, wait_until=wait_until, timeout=60_000)
        except PlaywrightTimeout:
            print(
                "Warning: Page load timed out after 60 s. "
                "Rendering whatever is available.",
                file=sys.stderr,
            )

        # Optional extra wait (e.g. for lazy-loaded images or animations)
        if wait_seconds > 0:
            print(f"  Waiting {wait_seconds:.1f}s for dynamic content…")
            time.sleep(wait_seconds)

        # Playwright PDF paper format mapping
        # Playwright expects e.g. "A4", "Letter", "Legal", "A3", "Tabloid"
        print(f"  Rendering PDF (format={media}, landscape={landscape}, scale={scale})…")
        page.pdf(
            path=output_path,
            format=media,
            landscape=landscape,
            scale=scale,
            print_background=True,        # include background colors/images
            margin={                       # sensible print margins
                "top":    "1cm",
                "bottom": "1cm",
                "left":   "1cm",
                "right":  "1cm",
            },
        )

        browser.close()

    pdf_size = Path(output_path).stat().st_size / 1024
    print(f"  PDF saved ({pdf_size:.1f} KB): {output_path}")


def print_url(
    url: str,
    printer_name: str | None = None,
    duplex: bool | None = None,
    copies: int = 1,
    landscape: bool = False,
    media: str = "A4",
    scale: float = 1.0,
    wait_seconds: float = 0.0,
    wait_for_network: bool = True,
    viewport_width: int = 1280,
    title: str | None = None,
) -> None:
    """
    Render a web page to PDF and send it to a CUPS printer.

    Args:
        url:              Web page URL to print.
        printer_name:     CUPS printer name (None = use .env / CUPS default).
        duplex:           True = duplex, False = simplex, None = read from .env.
        copies:           Number of copies.
        landscape:        True = landscape PDF orientation.
        media:            Paper size (e.g. "A4", "Letter").
        scale:            CSS scale factor for the PDF render (0.1–2.0).
        wait_seconds:     Extra seconds to wait after page load before render.
        wait_for_network: Wait for network idle before rendering.
        viewport_width:   Chromium viewport width in pixels.
        title:            CUPS job title (defaults to page URL).
    """
    url = validate_url(url)

    # Resolve duplex from .env if not explicitly set
    if duplex is None:
        duplex = _str_to_bool(os.getenv("DEFAULT_DUPLEX", "false"))

    conn = get_cups_connection()
    resolved_printer = resolve_printer(conn, printer_name)
    options = build_print_options(duplex=duplex, copies=copies, media=media)
    job_title = title or url

    print(f"\nPrint job summary:")
    print(f"  URL     : {url}")
    print(f"  Printer : {resolved_printer}")
    print(f"  Sides   : {'duplex (two-sided)' if duplex else 'simplex (one-sided)'}")
    print(f"  Copies  : {copies}")
    print(f"  Media   : {media}")
    print(f"  Orient. : {'landscape' if landscape else 'portrait'}")
    print(f"  Scale   : {scale}")
    print()

    # Render to a temporary PDF file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="print_url_") as tmp:
        tmp_path = tmp.name

    try:
        render_url_to_pdf(
            url=url,
            output_path=tmp_path,
            landscape=landscape,
            media=media,
            scale=scale,
            wait_seconds=wait_seconds,
            wait_for_network=wait_for_network,
            viewport_width=viewport_width,
        )

        # Submit to CUPS
        print(f"\n  Submitting to CUPS printer '{resolved_printer}'…")
        try:
            job_id = conn.printFile(
                printer=resolved_printer,
                filename=tmp_path,
                title=job_title,
                options=options,
            )
            print(f"\n✓ Print job submitted successfully.")
            print(f"  Job ID  : {job_id}")
            print(f"  Monitor : lpstat -o {resolved_printer}")
            print(f"  Cancel  : cancel {job_id}\n")
        except cups.IPPError as exc:
            err_code, err_msg = exc.args
            print(f"Error: CUPS rejected the print job.", file=sys.stderr)
            print(f"  Code   : {err_code}", file=sys.stderr)
            print(f"  Message: {err_msg}", file=sys.stderr)
            sys.exit(1)
    finally:
        # Always clean up the temporary PDF
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    env_printer = os.getenv("DEFAULT_PRINTER", "not set")
    env_duplex  = os.getenv("DEFAULT_DUPLEX",  "false")

    parser = argparse.ArgumentParser(
        description=(
            "Render a web page with headless Chromium and print it via CUPS.\n"
            "Supports JavaScript, CSS, and dynamic content."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Current .env defaults (from {_DOTENV_PATH}):\n"
            f"  DEFAULT_PRINTER = {env_printer}\n"
            f"  DEFAULT_DUPLEX  = {env_duplex}\n\n"
            "Examples:\n"
            "  python print_url.py --url https://example.com\n"
            "  python print_url.py --url https://news.ycombinator.com --duplex\n"
            "  python print_url.py --url https://example.com --printer HP_LJ --landscape\n"
            "  python print_url.py --url https://example.com --scale 0.8 --wait 3\n"
            "  python print_url.py --url https://example.com --no-network-wait\n"
        ),
    )

    parser.add_argument(
        "--url", "-u",
        required=True,
        metavar="URL",
        help="Web page URL to print (e.g. https://example.com).",
    )
    parser.add_argument(
        "--printer", "-p",
        default=None,
        metavar="NAME",
        help="CUPS printer name. Overrides DEFAULT_PRINTER from .env.",
    )

    sides_group = parser.add_mutually_exclusive_group()
    sides_group.add_argument(
        "--duplex", "-d",
        action="store_true",
        default=None,
        help="Print two-sided (duplex).",
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
        help="Number of copies (default: 1).",
    )
    parser.add_argument(
        "--landscape", "-l",
        action="store_true",
        help="Render and print in landscape orientation (default: portrait).",
    )
    parser.add_argument(
        "--media", "-m",
        default="A4",
        metavar="SIZE",
        help='Paper size: A4, Letter, Legal, A3, Tabloid, … (default: A4).',
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        metavar="FACTOR",
        help=(
            "CSS scale factor for the PDF render, between 0.1 and 2.0 "
            "(default: 1.0). Use 0.8 to shrink wide pages to fit."
        ),
    )
    parser.add_argument(
        "--wait", "-w",
        type=float,
        default=0.0,
        metavar="SECONDS",
        dest="wait_seconds",
        help=(
            "Extra seconds to wait after page load before rendering. "
            "Useful for pages with delayed animations or lazy content (default: 0)."
        ),
    )
    parser.add_argument(
        "--no-network-wait",
        action="store_false",
        dest="wait_for_network",
        default=True,
        help=(
            "Do not wait for network idle before rendering. "
            "Use for live dashboards or pages that stream data continuously."
        ),
    )
    parser.add_argument(
        "--viewport-width",
        type=int,
        default=1280,
        metavar="PX",
        help="Chromium viewport width in pixels (default: 1280).",
    )
    parser.add_argument(
        "--title", "-t",
        default=None,
        metavar="TITLE",
        help="CUPS job title shown in the print queue (default: the URL).",
    )

    args = parser.parse_args()

    # Validate scale
    if not (0.1 <= args.scale <= 2.0):
        print("Error: --scale must be between 0.1 and 2.0.", file=sys.stderr)
        sys.exit(1)

    # Validate copies
    if args.copies < 1:
        print("Error: --copies must be at least 1.", file=sys.stderr)
        sys.exit(1)

    # Resolve duplex flag
    if args.simplex:
        duplex_value: bool | None = False
    elif args.duplex:
        duplex_value = True
    else:
        duplex_value = None  # resolved from .env inside print_url()

    print_url(
        url=args.url,
        printer_name=args.printer,
        duplex=duplex_value,
        copies=args.copies,
        landscape=args.landscape,
        media=args.media,
        scale=args.scale,
        wait_seconds=args.wait_seconds,
        wait_for_network=args.wait_for_network,
        viewport_width=args.viewport_width,
        title=args.title,
    )


if __name__ == "__main__":
    main()
