import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from app/)
load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Add it to the .env file in the project root: ANTHROPIC_API_KEY=sk-ant-..."
    )

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = "phi3:3.8b"
CLAUDE_MODEL: str = "claude-haiku-4-5"
