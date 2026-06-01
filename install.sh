#!/bin/bash
# install.sh — Install mkai and configure shell integration (macOS / zsh)
set -e

echo "=== mkai installer ==="
echo ""

# Install the Python package
echo "→ Installing mkai via pip..."
pip3 install --user -e "$(dirname "$0")" 2>&1 | tail -1

# Ensure ~/.local/bin is on PATH
LOCAL_BIN="$HOME/.local/bin"
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    echo "→ Adding $LOCAL_BIN to PATH in ~/.zshrc..."
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    export PATH="$LOCAL_BIN:$PATH"
fi

# Add shell functions for mkdir --ai integration and cd support
MARKER="### mkai shell integration"
FUNCTION='
### mkai shell integration
mkdir() {
    if [[ "$1" == "--ai" ]]; then
        shift
        eval $(command mkai "$@")
    else
        command mkdir "$@"
    fi
}
### end mkai shell integration
'

ZSHRC="$HOME/.zshrc"

if grep -qF "$MARKER" "$ZSHRC" 2>/dev/null; then
    echo "→ Shell integration already present in ~/.zshrc"
else
    echo "→ Adding shell integration to ~/.zshrc..."
    echo "$FUNCTION" >> "$ZSHRC"
    echo "  Added. Run 'source ~/.zshrc' or open a new terminal to activate."
fi

echo ""
echo "=== Done! ==="
echo ""
echo "Usage:"
echo "  mkdir --ai '项目描述'  # Create a project dir with AI-generated name"
echo "  mkai '项目描述'        # Same, using mkai directly"
echo "  mkai --setup           # Configure AI providers"
echo "  mkai --list-providers  # Show configured providers"
echo ""
echo "If this is your first time, run: source ~/.zshrc"
echo "Then: mkai --setup"
