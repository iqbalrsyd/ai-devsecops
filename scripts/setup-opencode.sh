#!/bin/bash
# Setup opencode on VPS
# - Install ripgrep & fzf (optional but recommended)
# - Create config with proper API provider
# - Set env vars for OpenCode
# - Test opencode works

set -e

echo "=== Setup OpenCode on VPS ==="

# 1. Install ripgrep & fzf (recommended deps)
echo "[1/6] Installing ripgrep & fzf..."
if command -v apt &>/dev/null; then
    sudo apt install -y ripgrep fzf 2>&1 | tail -3
fi

# 2. Check opencode installed
echo "[2/6] Verify opencode installed..."
which opencode
opencode --version

# 3. List available agents
echo ""
echo "[3/6] Available agents:"
opencode agent list 2>&1 | head -20

# 4. Create config dir + minimal config
echo ""
echo "[4/6] Create config dir..."
mkdir -p ~/.config/opencode

# Use OpenCode provider with the known-working key
cat > ~/.config/opencode/opencode.json <<'JSON'
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "opencode": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OpenCode",
      "options": {
        "baseURL": "https://opencode.ai/zen/go/v1",
        "apiKey": "{env:OPENCODE_API_KEY}"
      },
      "models": {
        "minimax-m3": {
          "name": "minimax-m3"
        }
      }
    }
  },
  "model": "opencode/minimax-m3",
  "agent": {
    "default": "coder"
  }
}
JSON

echo "Config created at ~/.config/opencode/opencode.json"
cat ~/.config/opencode/opencode.json

# 5. Set env vars (API key from .env or input)
echo ""
echo "[5/6] Set API key in ~/.bashrc..."
ENV_FILE="/opt/ai-devsecops/.env"
if [ -f "$ENV_FILE" ]; then
    OPENCODE_KEY=$(grep "^OPENCODE_API_KEY=" "$ENV_FILE" | cut -d= -f2-)
    if [ -n "$OPENCODE_KEY" ] && [ "$OPENCODE_KEY" != "sk" ]; then
        # Backup bashrc
        cp ~/.bashrc ~/.bashrc.bak.$(date +%Y%m%d_%H%M%S)
        # Remove existing OPENCODE_API_KEY lines
        sed -i '/^export OPENCODE_API_KEY=/d' ~/.bashrc
        sed -i '/^export OPENCODE_BASE_URL=/d' ~/.bashrc
        sed -i '/^export OPENCODE_MODEL=/d' ~/.bashrc
        # Add new
        echo "export OPENCODE_API_KEY=\"$OPENCODE_KEY\"" >> ~/.bashrc
        echo "export OPENCODE_BASE_URL=\"https://opencode.ai/zen/go/v1\"" >> ~/.bashrc
        echo "export OPENCODE_MODEL=\"minimax-m3\"" >> ~/.bashrc
        echo "  Updated ~/.bashrc with API key (length: ${#OPENCODE_KEY})"
    fi
fi

# Also export in current shell
export OPENCODE_API_KEY="$OPENCODE_KEY"
export OPENCODE_BASE_URL="https://opencode.ai/zen/go/v1"
export OPENCODE_MODEL="minimax-m3"

# 6. Test
echo ""
echo "[6/6] Test opencode works..."
echo "  Test 1: opencode --version"
opencode --version 2>&1 | head -3
echo ""
echo "  Test 2: opencode agent list"
opencode agent list 2>&1 | head -10
echo ""
echo "  Test 3: opencode -p 'Reply with just: OK' (no agent)"
opencode -p "Reply with just the word: HELLO" 2>&1 | head -5
echo ""
echo "=== Setup complete! ==="
echo "Run 'opencode' to start interactive mode"
echo "Or: opencode -p \"your question\""
