#!/usr/bin/env bash
# deploy.sh - Set up Bot Squad on a fresh machine.
# Usage: ./deploy.sh
#
# Tested on: Windows (git-bash), macOS, Linux

set -e

echo "=== Bot Squad Deploy ==="
echo ""

# Check Python
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "[ERROR] Python 3 not found. Install it first."
    exit 1
fi
PY=$(command -v python3 || command -v python)
echo "[OK] Python: $($PY --version)"

# Install deps
echo "[..] Installing dependencies..."
$PY -m pip install pyyaml psutil 2>&1 | tail -3 || {
    echo "[WARN] pip install failed, trying uv..."
    uv pip install pyyaml psutil --system 2>&1 | tail -3 || {
        echo "[ERROR] Could not install deps. Install pyyaml + psutil manually."
        exit 1
    }
}

# Make scripts executable
chmod +x scripts/*.py 2>/dev/null || true
echo "[OK] Scripts are executable"

# Test run
echo ""
echo "[..] Running test pipeline..."
$PY scripts/orchestrator.py 2>&1 | tail -10

# Schedule
echo ""
echo "=== Scheduling ==="
echo ""
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "Windows detected. To schedule, run:"
    echo "  powershell -ExecutionPolicy Bypass -File scripts/register-task.ps1"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS detected. To schedule, add this to your crontab:"
    echo "  0 */2 * * * cd $(pwd) && $PY scripts/orchestrator.py"
    echo "Run: crontab -e"
else
    echo "Linux detected. To schedule, add this to your crontab:"
    echo "  0 */2 * * * cd $(pwd) && $PY scripts/orchestrator.py"
    echo "Run: crontab -e"
fi

echo ""
echo "=== Done ==="
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml — set your PRL wallet, Telegram chat_id, thresholds"
echo "  2. Set TELEGRAM_BOT_TOKEN env var (if using Telegram alerts)"
echo "  3. Schedule the task (see above)"
echo "  4. Check logs/ for the first scheduled run"
