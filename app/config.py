import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from app/)
load_dotenv(Path(__file__).parent.parent / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

if not ANTHROPIC_API_KEY:
    # Fallback: read from AWS SSM Parameter Store (used on EC2).
    # Region is fetched from EC2 IMDS (IMDSv2) so boto3 doesn't need
    # AWS_DEFAULT_REGION set in the environment.
    try:
        import urllib.request
        import boto3

        _token_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            method="PUT",
        )
        with urllib.request.urlopen(_token_req, timeout=2) as _r:
            _token = _r.read().decode()
        _region_req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/placement/region",
            headers={"X-aws-ec2-metadata-token": _token},
        )
        with urllib.request.urlopen(_region_req, timeout=2) as _r:
            _region = _r.read().decode()

        ssm = boto3.client("ssm", region_name=_region)
        response = ssm.get_parameter(
            Name="/chat-anonymiser/anthropic-api-key",
            WithDecryption=True,
        )
        ANTHROPIC_API_KEY = response["Parameter"]["Value"]
    except Exception:
        pass

if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Add it to .env (local) or SSM Parameter Store at "
        "/chat-anonymiser/anthropic-api-key (EC2)."
    )

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = "phi3:3.8b"
CLAUDE_MODEL: str = "claude-haiku-4-5"
