#!/bin/bash
set -euo pipefail


# ---------------------------------------------------------------------------
# Check system requirements
# ---------------------------------------------------------------------------

echo ""
echo "==> Checking system requirements..."
if ! command -v lpstat &>/dev/null; then
    echo ""
    echo "ERROR: CUPS is not installed."
    echo "       Install it with:"
    echo "         sudo apt install cups        # Debian/Ubuntu/Raspberry Pi OS"
    echo "         sudo dnf install cups        # Fedora/RHEL"
    echo "       Then start the service: sudo systemctl enable --now cups"
    echo ""
    exit 1
fi
echo "    CUPS found: $(lpstat -v 2>/dev/null | wc -l) printer(s) configured."


# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "==> Installing dependencies..."
uv sync --no-dev --project "$SKILL_ROOT"
uv run --project "$SKILL_ROOT" playwright install chromium
chmod +x "$SKILL_ROOT/bin/printer"
echo "    Done."

# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

echo ""
read -rp "==> Add bin/printer to the Openclaw approvals allowlist? [y/N] " REPLY
if [[ "${REPLY,,}" == "y" ]]; then

    echo ""
    echo "    For which agent should the allowlist entry apply?"
    read -rp "    Agent name (or * for all agents): " AGENT_INPUT
    AGENT="${AGENT_INPUT:-*}"

    openclaw approvals allowlist add --agent "$AGENT" "**/printer/bin/printer"
    echo "    Allowlist entry added for agent: $AGENT"
else
    echo "    Skipping allowlist setup."
fi


echo ""
echo "==> Setup complete."
