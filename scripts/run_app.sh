#!/usr/bin/env bash
# Kavach Launch Script
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"
export PYTHONPATH="$DIR:${PYTHONPATH:-}"

# Ensure standard Python framework bin dirs and user local bin dirs are on PATH
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$HOME/Library/Python/3.13/bin:$HOME/.local/bin:$PATH"

# Resolve python binary
if [ -x "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" ]; then
    PY_BIN="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
elif command -v python3 &> /dev/null; then
    PY_BIN="python3"
elif command -v python &> /dev/null; then
    PY_BIN="python"
else
    PY_BIN="python3"
fi

echo "🛡️ Starting Kavach Sovereign AI Workbench..."
if command -v streamlit &> /dev/null; then
    streamlit run src/app/streamlit_app.py --server.port 8501 --server.address localhost
else
    "$PY_BIN" -m streamlit run src/app/streamlit_app.py --server.port 8501 --server.address localhost
fi
