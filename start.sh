#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve &
  sleep 2
fi

cd "$PROJECT_ROOT/app"

if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$PROJECT_ROOT/.venv"
fi

source "$PROJECT_ROOT/.venv/bin/activate"

echo "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -q -r requirements.txt

echo ""
echo "Open http://localhost:8000 in your browser"
echo ""
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
