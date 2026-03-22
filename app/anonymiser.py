"""
Calls phi3:mini via Ollama to detect PII entities in text.
The backend (session_store + main.py) performs the actual text replacement.
"""

import json
import re
import httpx
from config import OLLAMA_BASE_URL, OLLAMA_MODEL

OLLAMA_TIMEOUT = 120.0  # phi3:mini can be slow on first run

SYSTEM_PROMPT = (
    "Your job is to find PII and other sensitive information in text and list it as a JSON array. Each item has two fields: \"value\" (exact substring from the text) and \"type\". Try to match the type with one of the following PII categories: NAME, EMAIL, PHONE, ADDRESS, COMPANY, URL, SSN, USERNAME, JOB, DOB, FINANCE, IP_ADDRESS, COORDINATES, WBS_CODE or with OTHER_PII if match with other categories in impossible. Output only the JSON array and nothing else."
)

USER_PROMPT_TEMPLATE = """Find all potential sensitive information PII in this text:

{text}

JSON output:"""


def _extract_json_array(raw: str) -> list[dict]:
    """Extract the first JSON array found in raw string (model may wrap it in prose)."""
    raw = raw.strip()
    # Try direct parse first
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Find first [...] block
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return []


async def detect_entities(text: str) -> list[dict]:
    """
    Returns a list of detected entities, e.g.:
    [{"value": "Jane Doe", "type": "NAME"}, {"value": "jane@acme.com", "type": "EMAIL"}]

    Raises httpx.ConnectError if Ollama is unreachable.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": USER_PROMPT_TEMPLATE.format(text=text),
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.2},
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    raw_output = data.get("response", "")
    entities = _extract_json_array(raw_output)

    # Validate and normalise: keep only entries with non-empty value and known/unknown type
    valid_types = {
        "NAME", "EMAIL", "ADDRESS", "COMPANY", "PHONE", "URL", "SSN",
        "USERNAME", "DOB", "FINANCE", "IP_ADDRESS", "COORDINATES",
        "WBS_CODE", "OTHER_PII",
    }
    cleaned = []
    seen_values = set()
    for item in entities:
        value = (item.get("value") or "").strip()
        entity_type = (item.get("type") or "OTHER_PII").upper()
        if not value or value in seen_values:
            continue
        if entity_type not in valid_types:
            entity_type = "OTHER_PII"
        seen_values.add(value)
        cleaned.append({"value": value, "type": entity_type})

    return cleaned


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """
    Replace original values with placeholders.
    replacements: { "[NAME_1]": "Jane Doe", ... }
    Sorted longest-first to avoid partial-match collisions.
    """
    # Invert: original → placeholder
    pairs = sorted(
        ((original, placeholder) for placeholder, original in replacements.items()),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for original, placeholder in pairs:
        text = text.replace(original, placeholder)
    return text


def restore_replacements(text: str, replacements: dict[str, str]) -> tuple[str, list[dict]]:
    """
    Replace placeholders with original values.
    replacements: { "[NAME_1]": "Jane Doe", ... }
    Returns (restored_text, highlighted_ranges) where each range is
    {"start": int, "end": int, "placeholder": str, "original": str}.
    Sorted longest-placeholder-first to avoid partial collisions.
    """
    pairs = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
    ranges: list[dict] = []

    for placeholder, original in pairs:
        start = 0
        while True:
            idx = text.find(placeholder, start)
            if idx == -1:
                break
            text = text[:idx] + original + text[idx + len(placeholder):]
            ranges.append({
                "start": idx,
                "end": idx + len(original),
                "fake": placeholder,
                "original": original,
            })
            start = idx + len(original)

    # Sort ranges by start position for the frontend
    ranges.sort(key=lambda r: r["start"])
    return text, ranges
