#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"


# ---------------------------------------------------------------------------
# Check system requirements
# ---------------------------------------------------------------------------

echo ""
echo "==> Checking system requirements..."
if ! command -v lpstat &>/dev/null; then
    echo ""
    echo "ERROR: CUPS is not installed."
    echo "       Install it with:"
    echo "         sudo apt install cups        # Debian/Ubuntu"
    echo "         brew install cups            # macOS (via Homebrew)"
    echo "       Then start the service: sudo systemctl enable --now cups"
    echo ""
    exit 1
fi
echo "    CUPS found: $(lpstat -v 2>/dev/null | wc -l) printer(s) configured."


# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------

echo ""
echo "==> Installing dependencies..."
uv sync --no-dev --project "$SKILL_ROOT"
uv run --project "$SKILL_ROOT" playwright install chromium
chmod +x "$SKILL_ROOT/bin/printit"
echo "    Done."


# ---------------------------------------------------------------------------
# Patch SKILL.md for Claude Code
# ---------------------------------------------------------------------------

SKILL_MD="$SKILL_ROOT/SKILL.md"
if [[ -f "$SKILL_MD" ]]; then
    sed -i '' \
        -e 's|{baseDir}/||g' \
        -e '/^licence:/d' \
        -e '/^metadata:/d' \
        "$SKILL_MD" 2>/dev/null || \
    sed -i \
        -e 's|{baseDir}/||g' \
        -e '/^licence:/d' \
        -e '/^metadata:/d' \
        "$SKILL_MD"
    echo "    SKILL.md patched for Claude Code."
fi
echo "    Done."


echo ""
echo "==> Setup complete."
