# Printer Skill – Setup Guide


## Installation as Openclaw Skill

### 1 – Unzip the skill package

Unzip `printer.skill_vN.N.N.zip` into one of:

- `~/.openclaw/skills/` — available to all agents
- `~/.openclaw/workspace/<agent>/skills/` — available to a specific agent only

### 2 – Run the setup script

```bash
cd ~/.openclaw/skills/printer   # or the agent-specific path
bash setup/setup-openclaw.sh
```

The script performs the following steps:

1. **Check CUPS** — verifies that CUPS is installed and running. Exits with install instructions if not found.
2. **Install dependencies** — runs `uv sync --no-dev`, installs Chromium via Playwright, and makes `bin/printer` executable.
3. **Allowlist** — offers to add `bin/printer` to the Openclaw approvals allowlist. You can restrict the entry to a specific agent name or use `*` for all agents.

---

## Installation as Claude Code Skill

### 1 – Unzip the skill package

Unzip `printer.skill_vN.N.N.zip` into `~/.claude/skills/`:

```bash
unzip printer.skill_vN.N.N.zip -d ~/.claude/skills/
```

### 2 – Run the setup script

```bash
cd ~/.claude/skills/printer
bash setup/setup-claude.sh
```

The script performs the following steps:

1. **Check CUPS** — verifies that CUPS is installed and running. Exits with install instructions if not found.
2. **Install dependencies** — runs `uv sync --no-dev`, installs Chromium via Playwright, and makes `bin/printer` executable.
3. **Patch `SKILL.md` for Claude Code** — removes the `{baseDir}/` path prefix from all commands and strips Openclaw-only frontmatter fields (`licence`, `metadata`).

---

## System Requirements

- **CUPS** must be installed and running.
  - Debian/Ubuntu/Raspberry Pi OS: `sudo apt install cups && sudo systemctl enable --now cups`
  - macOS: pre-installed; manage via `cupsctl`
- **Chromium** is installed automatically by the setup script via `playwright install chromium`.
- **Python ≥ 3.13** and **uv** must be available.
