#!/usr/bin/env python3
"""
print_text.py
-------------
Convert a plain text file to a PDF with configurable font and font size,
then send it to a CUPS printer. Uses ReportLab for PDF generation, which
gives full control over typeface, size, line spacing, and margins.

The .env file in the skill root directory can define a default printer and
default duplex setting (see .env.example).

Usage:
    python print_text.py --file notes.txt
    python print_text.py --file notes.txt --font Helvetica --font-size 11
    python print_text.py --file notes.txt --font Courier --font-size 9 --duplex
    python print_text.py --file notes.txt --printer "HP_LaserJet" --copies 2
    python print_text.py --file notes.txt --line-spacing 1.5 --margin 2cm
    python print_text.py --help

Available built-in ReportLab fonts (no extra files needed):
    Courier, Courier-Bold, Courier-Oblique, Courier-BoldOblique
    Helvetica, Helvetica-Bold, Helvetica-Oblique, Helvetica-BoldOblique
    Times-Roman, Times-Bold, Times-Italic, Times-BoldItalic
    Symbol, ZapfDingbats

First-time setup:
    uv sync          # install all dependencies from pyproject.toml
    playwright install chromium   # only needed for print_url.py

Requirements:
    - pycups        (Python CUPS bindings)
    - python-dotenv (read .env configuration)
    - reportlab     (PDF generation)
    - CUPS must be installed and running on the system
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

# ── Load .env from the skill root (one level above scripts/) ──────────────────
_SKILL_ROOT  = Path(__file__).parent.parent.resolve()
_DOTENV_PATH = _SKILL_ROOT / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_DOTENV_PATH)
except ImportError:
    print(
        "Warning: 'python-dotenv' is not installed. .env file will be ignored.\n"
        "Install with: uv sync",
        file=sys.stderr,
    )

try:
    import cups
except ImportError:
    print("Error: 'pycups' is not installed. Run: uv sync", file=sys.stderr)
    sys.exit(1)

from utils import _str_to_bool, get_cups_connection, resolve_printer, build_print_options  # noqa: E402

try:
    from reportlab.lib.pagesizes import A4, LETTER, A3, LEGAL
    from reportlab.lib.units import cm, mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
except ImportError:
    print("Error: 'reportlab' is not installed. Run: uv sync", file=sys.stderr)
    sys.exit(1)


# ── Constants ─────────────────────────────────────────────────────────────────

PAPER_SIZES: dict[str, tuple] = {
    "A4":     A4,
    "A3":     A3,
    "Letter": LETTER,
    "Legal":  LEGAL,
}

# All built-in ReportLab fonts (no external files required)
BUILTIN_FONTS: list[str] = [
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Symbol", "ZapfDingbats",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_margin(value: str) -> float:
    """
    Parse a margin string and return the value in ReportLab points.

    Accepted formats:
        "2cm"   → 2 centimetres
        "20mm"  → 20 millimetres
        "72"    → 72 points (raw float/int, treated as points)

    Args:
        value: Margin string from the CLI.

    Returns:
        Margin in ReportLab points (1 pt = 1/72 inch).

    Raises:
        ValueError: If the format is not recognised.
    """
    value = value.strip().lower()
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(cm|mm|pt|in)?", value)
    if not m:
        raise ValueError(f"Cannot parse margin value: '{value}'")
    number = float(m.group(1))
    unit   = m.group(2) or "pt"
    return {"cm": cm, "mm": mm, "pt": 1.0, "in": 72.0}[unit] * number


# ── PDF generation ─────────────────────────────────────────────────────────────

def text_to_pdf(
    text_path: Path,
    output_path: str,
    font: str = "Courier",
    font_size: float = 10.0,
    line_spacing: float = 1.2,
    media: str = "A4",
    landscape: bool = False,
    margin: float = 2.0 * cm,
    encoding: str = "utf-8",
) -> None:
    """
    Render a plain text file to a PDF using ReportLab.

    Each line of the source file is placed on the canvas with the chosen
    font and size. Long lines are wrapped at the right margin. A new page
    is started automatically when the bottom margin is reached.

    Args:
        text_path:    Path to the source .txt file.
        output_path:  Destination PDF file path.
        font:         ReportLab font name (must be a built-in or registered font).
        font_size:    Font size in points.
        line_spacing: Multiplier applied to font_size to get line height
                      (1.0 = tight, 1.2 = normal, 1.5 = loose).
        media:        Paper size key: "A4", "Letter", "A3", "Legal".
        landscape:    If True, swap width and height for landscape orientation.
        margin:       Page margin in ReportLab points (use cm/mm helpers).
        encoding:     Text file encoding (default: utf-8).
    """
    # Validate font
    if font not in BUILTIN_FONTS:
        available = ", ".join(BUILTIN_FONTS)
        print(
            f"Warning: Font '{font}' is not a recognised built-in ReportLab font.\n"
            f"Available: {available}\n"
            f"Falling back to 'Courier'.",
            file=sys.stderr,
        )
        font = "Courier"

    # Page size
    page_size = PAPER_SIZES.get(media, A4)
    if landscape:
        page_size = (page_size[1], page_size[0])   # swap width/height

    page_width, page_height = page_size
    line_height = font_size * line_spacing

    # Usable text area
    text_width  = page_width  - 2 * margin
    text_height = page_height - 2 * margin

    # Read source text
    try:
        lines = text_path.read_text(encoding=encoding).splitlines()
    except UnicodeDecodeError:
        print(
            f"Warning: Could not read file as {encoding}. Trying latin-1.",
            file=sys.stderr,
        )
        lines = text_path.read_text(encoding="latin-1").splitlines()

    # ── ReportLab canvas ──────────────────────────────────────────────────────
    c = canvas.Canvas(output_path, pagesize=page_size)
    c.setFont(font, font_size)

    # Estimate max characters per line using average glyph width
    # pdfmetrics.stringWidth returns width in points for the given font/size
    avg_char_width = pdfmetrics.stringWidth("M", font, font_size)
    chars_per_line = max(1, int(text_width / avg_char_width))

    def new_page() -> float:
        """Start a fresh page and return the initial y cursor."""
        c.showPage()
        c.setFont(font, font_size)
        return page_height - margin - font_size

    y = page_height - margin - font_size   # starting y position

    for raw_line in lines:
        # Expand tabs to spaces (4-space tab stop)
        raw_line = raw_line.expandtabs(4)

        # Word-wrap long lines
        if not raw_line:
            # Blank line → just advance cursor
            wrapped = [""]
        elif pdfmetrics.stringWidth(raw_line, font, font_size) <= text_width:
            wrapped = [raw_line]
        else:
            # Simple word-wrap
            wrapped = []
            words   = raw_line.split(" ")
            current = ""
            for word in words:
                test = (current + " " + word).lstrip()
                if pdfmetrics.stringWidth(test, font, font_size) <= text_width:
                    current = test
                else:
                    if current:
                        wrapped.append(current)
                    # If a single word is still too long, split by characters
                    while pdfmetrics.stringWidth(word, font, font_size) > text_width:
                        split_at = max(1, chars_per_line)
                        wrapped.append(word[:split_at])
                        word = word[split_at:]
                    current = word
            if current:
                wrapped.append(current)

        for segment in wrapped:
            if y < margin + line_height:
                y = new_page()
            c.drawString(margin, y, segment)
            y -= line_height

    c.save()
    pdf_size = Path(output_path).stat().st_size / 1024
    print(f"  PDF generated ({pdf_size:.1f} KB): {output_path}")


# ── Main workflow ─────────────────────────────────────────────────────────────

def print_text(
    file_path: str,
    printer_name: str | None = None,
    duplex: bool | None = None,
    copies: int = 1,
    font: str = "Courier",
    font_size: float = 10.0,
    line_spacing: float = 1.2,
    media: str = "A4",
    landscape: bool = False,
    margin_str: str = "2cm",
    encoding: str = "utf-8",
    title: str | None = None,
) -> None:
    """
    Convert a text file to PDF and send it to a CUPS printer.

    Args:
        file_path:    Path to the text file to print.
        printer_name: CUPS printer name (None = .env / CUPS default).
        duplex:       True = duplex, False = simplex, None = read from .env.
        copies:       Number of copies.
        font:         ReportLab font name.
        font_size:    Font size in points.
        line_spacing: Line height multiplier (1.0 tight … 1.5 loose).
        media:        Paper size: "A4", "Letter", "A3", "Legal".
        landscape:    Landscape orientation.
        margin_str:   Margin string, e.g. "2cm", "15mm", "72pt".
        encoding:     Source file encoding.
        title:        CUPS job title (defaults to filename).
    """
    resolved_path = Path(file_path).resolve()
    if not resolved_path.exists():
        print(f"Error: File not found: {resolved_path}", file=sys.stderr)
        sys.exit(1)

    # Resolve duplex from .env if not set
    if duplex is None:
        duplex = _str_to_bool(os.getenv("DEFAULT_DUPLEX", "false"))

    # Parse margin
    try:
        margin_pts = _parse_margin(margin_str)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    conn             = get_cups_connection()
    resolved_printer = resolve_printer(conn, printer_name)
    options          = build_print_options(duplex=duplex, copies=copies, media=media)
    job_title        = title or resolved_path.name

    print(f"\nPrint job summary:")
    print(f"  File      : {resolved_path}")
    print(f"  Printer   : {resolved_printer}")
    print(f"  Sides     : {'duplex (two-sided)' if duplex else 'simplex (one-sided)'}")
    print(f"  Copies    : {copies}")
    print(f"  Font      : {font} {font_size}pt")
    print(f"  Spacing   : {line_spacing}×")
    print(f"  Media     : {media}{'  (landscape)' if landscape else ''}")
    print(f"  Margin    : {margin_str}")
    print(f"  Encoding  : {encoding}")
    print()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="print_text_") as tmp:
        tmp_path = tmp.name

    try:
        text_to_pdf(
            text_path=resolved_path,
            output_path=tmp_path,
            font=font,
            font_size=font_size,
            line_spacing=line_spacing,
            media=media,
            landscape=landscape,
            margin=margin_pts,
            encoding=encoding,
        )

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
        Path(tmp_path).unlink(missing_ok=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    env_printer = os.getenv("DEFAULT_PRINTER", "not set")
    env_duplex  = os.getenv("DEFAULT_DUPLEX",  "false")

    parser = argparse.ArgumentParser(
        description=(
            "Convert a plain text file to PDF with a chosen font and print it via CUPS."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Current .env defaults (from {_DOTENV_PATH}):\n"
            f"  DEFAULT_PRINTER = {env_printer}\n"
            f"  DEFAULT_DUPLEX  = {env_duplex}\n\n"
            "Available built-in fonts:\n"
            "  Courier, Courier-Bold, Courier-Oblique, Courier-BoldOblique\n"
            "  Helvetica, Helvetica-Bold, Helvetica-Oblique, Helvetica-BoldOblique\n"
            "  Times-Roman, Times-Bold, Times-Italic, Times-BoldItalic\n\n"
            "Examples:\n"
            "  python print_text.py --file notes.txt\n"
            "  python print_text.py --file notes.txt --font Helvetica --font-size 11\n"
            "  python print_text.py --file log.txt --font Courier --font-size 8 --landscape\n"
            "  python print_text.py --file readme.txt --line-spacing 1.5 --margin 2.5cm\n"
        ),
    )

    parser.add_argument("--file",    "-f", required=True, metavar="PATH",
                        help="Path to the plain text file to print.")
    parser.add_argument("--printer", "-p", default=None, metavar="NAME",
                        help="CUPS printer name. Overrides DEFAULT_PRINTER from .env.")

    sides = parser.add_mutually_exclusive_group()
    sides.add_argument("--duplex",  "-d", action="store_true", default=None,
                       help="Print two-sided (duplex).")
    sides.add_argument("--simplex", "-s", action="store_true", default=None,
                       help="Print one-sided (simplex). Overrides DEFAULT_DUPLEX=true.")

    parser.add_argument("--copies", "-n", type=int, default=1, metavar="N",
                        help="Number of copies (default: 1).")
    parser.add_argument("--font", default="Courier", metavar="NAME",
                        help="ReportLab font name (default: Courier). See --help for list.")
    parser.add_argument("--font-size", type=float, default=10.0, metavar="PT",
                        help="Font size in points (default: 10).")
    parser.add_argument("--line-spacing", type=float, default=1.2, metavar="FACTOR",
                        help="Line height multiplier: 1.0=tight, 1.2=normal, 1.5=loose (default: 1.2).")
    parser.add_argument("--media", "-m", default="A4",
                        choices=list(PAPER_SIZES.keys()),
                        help="Paper size (default: A4).")
    parser.add_argument("--landscape", "-l", action="store_true",
                        help="Print in landscape orientation.")
    parser.add_argument("--margin", default="2cm", metavar="VALUE",
                        help="Page margin, e.g. '2cm', '15mm', '72pt' (default: 2cm).")
    parser.add_argument("--encoding", default="utf-8", metavar="ENC",
                        help="Source file character encoding (default: utf-8).")
    parser.add_argument("--title", "-t", default=None, metavar="TITLE",
                        help="CUPS job title (default: filename).")

    args = parser.parse_args()

    if args.font_size <= 0:
        print("Error: --font-size must be greater than 0.", file=sys.stderr)
        sys.exit(1)
    if args.line_spacing <= 0:
        print("Error: --line-spacing must be greater than 0.", file=sys.stderr)
        sys.exit(1)
    if args.copies < 1:
        print("Error: --copies must be at least 1.", file=sys.stderr)
        sys.exit(1)

    if args.simplex:
        duplex_value: bool | None = False
    elif args.duplex:
        duplex_value = True
    else:
        duplex_value = None

    print_text(
        file_path=args.file,
        printer_name=args.printer,
        duplex=duplex_value,
        copies=args.copies,
        font=args.font,
        font_size=args.font_size,
        line_spacing=args.line_spacing,
        media=args.media,
        landscape=args.landscape,
        margin_str=args.margin,
        encoding=args.encoding,
        title=args.title,
    )


if __name__ == "__main__":
    main()
