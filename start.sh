#!/usr/bin/env bash
set -e

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve &
  sleep 2
fi

cd "$(dirname "$0")/app"

if [ ! -d "../.venv" ]; then
  python3 -m venv ../.venv
fi
source ../.venv/bin/activate

pip install -q -r requirements.txt
echo "Open http://localhost:8000 in your browser"
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
