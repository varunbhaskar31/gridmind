#!/usr/bin/env bash
# GridMind One-Command Demo Launcher
set -e

echo "=================================================================="
echo "⚡ Starting GridMind — Agentic Renewable Energy Orchestrator ⚡"
echo " Deployed for Deccan Renewables Pvt. Ltd. (Karnataka, India)"
echo "=================================================================="

# Determine project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Activate virtual environment if available
if [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
fi

# Ensure mock LLM mode is active if no Gemini API key is provided
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Notice: GEMINI_API_KEY is not set in environment. Running in offline MOCK_LLM mode."
    export MOCK_LLM=true
fi

# Launch Streamlit Control Room Dashboard
echo "Launching Streamlit Control Room UI on http://localhost:8501 ..."
streamlit run app/streamlit_app.py --server.headless=false --server.port=8501
