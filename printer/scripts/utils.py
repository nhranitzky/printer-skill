"""
utils.py
--------
Shared helpers for all printer skill scripts.
"""

import sys

import cups


def _str_to_bool(value: str) -> bool:
    """Convert a string like 'true'/'false'/'1'/'0' to a Python bool."""
    return value.strip().lower() in ("true", "1", "yes")


def get_cups_connection() -> cups.Connection:
    """Return a CUPS connection or exit with an error message."""
    try:
        return cups.Connection()
    except RuntimeError as exc:
        print(f"Error: Could not connect to CUPS. Is CUPS running?\nDetails: {exc}", file=sys.stderr)
        sys.exit(1)


def resolve_printer(conn: cups.Connection, requested: str | None) -> str:
    """
    Determine the target printer name.

    Priority:
        1. --printer CLI argument
        2. CUPS system default printer
        3. First available printer (last resort)

    Args:
        conn:       An active CUPS connection.
        requested:  Value of --printer CLI argument, or None.

    Returns:
        The resolved printer name string.

    Raises:
        SystemExit: If no printer can be found at all.
    """
    available: dict = conn.getPrinters()

    if not available:
        print("Error: No printers are configured in CUPS.", file=sys.stderr)
        print("Add a printer via http://localhost:631 or `lpadmin`.", file=sys.stderr)
        sys.exit(1)

    if len(available) == 1 and not requested:
        return next(iter(available))

    # 1. Explicit CLI argument
    if requested:
        if requested not in available:
            print(f"Error: Printer '{requested}' not found in CUPS.", file=sys.stderr)
            print(f"Available printers: {', '.join(sorted(available.keys()))}", file=sys.stderr)
            sys.exit(1)
        return requested

    # 2. CUPS system default
    try:
        dests = conn.getDests()
        for (name, _instance), dest in dests.items():
            if dest.is_default and name:
                return name
    except Exception:
        pass

    # 3. First available printer
    first = sorted(available.keys())[0]
    print(f"Warning: No default printer set. Using first available: '{first}'", file=sys.stderr)
    return first


def build_print_options(
    duplex: bool,
    copies: int,
    media: str | None,
    orientation: str | None = None,
) -> dict[str, str]:
    """
    Build the CUPS options dictionary for the print job.

    Args:
        duplex:       True → two-sided (long-edge binding); False → one-sided.
        copies:       Number of copies to print.
        media:        Optional media/paper size string (e.g. "A4").
        orientation:  Optional orientation: "portrait" or "landscape".

    Returns:
        Dictionary of CUPS print options.
    """
    options: dict[str, str] = {}

    # Duplex / simplex
    if duplex:
        options["sides"] = "two-sided-long-edge"
    else:
        options["sides"] = "one-sided"

    # Copies
    if copies > 1:
        options["copies"] = str(copies)

    # Media
    if media:
        options["media"] = media

    # Orientation
    if orientation:
        orientation_map = {
            "portrait":  "3",
            "landscape": "4",
        }
        key = orientation.lower()
        if key in orientation_map:
            options["orientation-requested"] = orientation_map[key]
        else:
            print(f"Warning: Unknown orientation '{orientation}'. Ignoring.", file=sys.stderr)

    return options
