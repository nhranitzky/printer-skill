#!/usr/bin/env python3
"""
list_printers.py
----------------
Discovers and displays all printers available via CUPS on the local network.

Usage:
    python list_printers.py [--verbose]

Requirements:
    pip install pycups

Output:
    A formatted table showing printer name, URI, status, and whether
    it is the system default printer.
"""

import json
import sys

import click

try:
    import cups
except ImportError:
    print("Error: 'pycups' is not installed. Run: pip install pycups", file=sys.stderr)
    sys.exit(1)


def get_default_printer(conn: cups.Connection) -> str | None:
    """Return the name of the CUPS default printer, or None if not set."""
    try:
        dests = conn.getDests()
        for (name, instance), dest in dests.items():
            if dest.is_default:
                return name
    except Exception:
        pass
    return None


# ── State mapping ─────────────────────────────────────────────────────────────
_STATE_LABELS = {
    cups.IPP_PRINTER_IDLE:       "idle",
    cups.IPP_PRINTER_PROCESSING: "processing",
    cups.IPP_PRINTER_STOPPED:    "stopped",
}


def _collect_printers(conn: cups.Connection, verbose: bool) -> tuple[list[dict], str | None]:
    """Return (printer_list, default_printer_name)."""
    printers: dict = conn.getPrinters()
    default_printer = get_default_printer(conn)

    result = []
    for name, attrs in sorted(printers.items()):
        state_code = attrs.get("printer-state", -1)
        entry: dict = {
            "name":       name,
            "uri":        attrs.get("device-uri", "unknown"),
            "state":      _STATE_LABELS.get(state_code, f"unknown ({state_code})"),
            "is_default": name == default_printer,
        }
        if verbose:
            entry["attributes"] = {k: str(v) for k, v in sorted(attrs.items())}
        result.append(entry)

    return result, default_printer


def list_printers_json(conn: cups.Connection, verbose: bool = False) -> None:
    """Output printer list as JSON."""
    printers_data, default_printer = _collect_printers(conn, verbose)

    output = {
        "total":           len(printers_data),
        "default_printer": default_printer,
        "printers":        printers_data,
    }
    print(json.dumps(output, indent=2))


def list_printers_text(conn: cups.Connection, verbose: bool = False) -> None:
    """Output printer list as a formatted text table."""
    printers_data, default_printer = _collect_printers(conn, verbose)

    if not printers_data:
        print("No printers found. Make sure CUPS is running and printers are configured.")
        print("You can add printers via http://localhost:631 or the `lpadmin` command.")
        return

    col_name  = 30
    col_uri   = 45
    col_state = 12
    col_def   = 8
    separator = "-" * (col_name + col_uri + col_state + col_def + 9)

    print(f"\n{'Available Printers':^{col_name + col_uri + col_state + col_def + 9}}")
    print(separator)
    print(
        f"{'Name':<{col_name}} "
        f"{'URI':<{col_uri}} "
        f"{'State':<{col_state}} "
        f"{'Default':<{col_def}}"
    )
    print(separator)

    for entry in printers_data:
        uri = entry["uri"]
        if len(uri) > col_uri - 2:
            uri = uri[: col_uri - 5] + "..."
        is_default = "✓" if entry["is_default"] else ""

        print(
            f"{entry['name']:<{col_name}} "
            f"{uri:<{col_uri}} "
            f"{entry['state']:<{col_state}} "
            f"{is_default:<{col_def}}"
        )

        if verbose:
            for key, value in entry.get("attributes", {}).items():
                print(f"    {key}: {value}")

    print(separator)
    print(f"Total: {len(printers_data)} printer(s) found.\n")

    if default_printer:
        print(f"System default printer: {default_printer}")
    else:
        print("No system default printer is configured.")

    print()


@click.command("list-printers")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Include all CUPS attributes for each printer.")
@click.option("--text", is_flag=True, default=False,
              help="Output as a human-readable text table (default: JSON).")
def list_printers_cmd(verbose: bool, text: bool) -> None:
    """List all CUPS printers available on this system / network."""
    try:
        conn = cups.Connection()
    except RuntimeError as exc:
        raise click.ClickException(f"Could not connect to CUPS. Is CUPS running?\nDetails: {exc}")

    if not conn.getPrinters():
        if text:
            click.echo("No printers found. Make sure CUPS is running and printers are configured.")
            click.echo("You can add printers via http://localhost:631 or the `lpadmin` command.")
        else:
            click.echo(json.dumps({"total": 0, "default_printer": None, "printers": []}, indent=2))
        return

    if text:
        list_printers_text(conn, verbose=verbose)
    else:
        list_printers_json(conn, verbose=verbose)


if __name__ == "__main__":
    list_printers_cmd()
