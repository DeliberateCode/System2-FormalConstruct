#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<EOF
Usage: ./install.sh

Install the FormalConstruct CLI toolkit and Claude Code agent.
EOF
    exit 0
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

# ── Python version check ──

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major="${version%%.*}"
        minor="${version#*.}"
        if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "Error: Python >= 3.11 is required but not found on PATH."
    exit 1
fi

echo "Using $PYTHON ($("$PYTHON" --version))"

# ── Install Python package ──

if command -v pipx &>/dev/null; then
    echo "Installing via pipx..."
    pipx install "$REPO_DIR" --force
    echo "Installed: $(command -v formalconstruct)"

elif command -v uv &>/dev/null; then
    echo "Installing via uv..."
    uv tool install "$REPO_DIR" --force
    echo "Installed: $(command -v formalconstruct)"

else
    echo "Installing into local venv..."
    VENV_DIR="$REPO_DIR/.venv"
    if [[ ! -d "$VENV_DIR" ]]; then
        "$PYTHON" -m venv "$VENV_DIR"
    fi
    "$VENV_DIR/bin/pip" install -q "$REPO_DIR"

    LINK_DIR="$HOME/.local/bin"
    mkdir -p "$LINK_DIR"
    ln -sf "$VENV_DIR/bin/formalconstruct" "$LINK_DIR/formalconstruct"

    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$LINK_DIR"; then
        echo ""
        echo "Note: Add $LINK_DIR to your PATH:"
        echo "  export PATH=\"$LINK_DIR:\$PATH\""
    fi
    echo "Installed: $LINK_DIR/formalconstruct"
fi

echo ""
formalconstruct --version

# ── Install Claude Code agent and command ──

echo ""
echo "── Installing Claude Code agent ──"

CLAUDE_DIR="$REPO_DIR/.claude"
mkdir -p "$CLAUDE_DIR/agents" "$CLAUDE_DIR/commands"

cp "$REPO_DIR/plugin/agents/formalize.md" "$CLAUDE_DIR/agents/formalize.md"
echo "Installed agent: .claude/agents/formalize.md"

if [[ -f "$CLAUDE_DIR/commands/formalize.md" ]]; then
    echo "Command already exists: .claude/commands/formalize.md"
else
    cp "$REPO_DIR/.claude/commands/formalize.md" "$CLAUDE_DIR/commands/formalize.md" 2>/dev/null || true
    echo "Installed command: .claude/commands/formalize.md"
fi

# ── Register AXLE MCP server (user scope) ──

echo ""
echo "── Registering AXLE MCP server ──"

AXLE_ADD_CMD=(claude mcp add axle --scope user -- uvx --from axiom-axle-mcp axle-mcp-server)
if command -v claude &>/dev/null; then
    if claude mcp get axle &>/dev/null; then
        echo "AXLE MCP server already registered (user scope)."
    elif "${AXLE_ADD_CMD[@]}"; then
        echo "Registered AXLE MCP server (user scope)."
    else
        echo "Warning: could not register AXLE MCP server. Register manually with:"
        echo "  ${AXLE_ADD_CMD[*]}"
    fi
    if [[ -z "${AXLE_API_KEY:-}" ]]; then
        echo "Note: AXLE_API_KEY is not set. Add it to your shell profile (e.g. ~/.zshrc):"
        echo "  export AXLE_API_KEY=<your-key>"
    fi
else
    echo "Note: 'claude' CLI not found; skipping AXLE MCP registration. Register later with:"
    echo "  ${AXLE_ADD_CMD[*]}"
fi

echo ""
echo "Done."
