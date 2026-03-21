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
    "You are a PII detection assistant. Your only job is to find sensitive or identifying information in text and list it as a JSON array. Each item has two fields: \"value\" (exact substring from the text) and \"type\" (see categories). Categories: NAME, EMAIL, PHONE, ADDRESS, COMPANY, URL, SSN, USERNAME, DOB, FINANCE, IP_ADDRESS, COORDINATES, WBS_CODE, OTHER_PII. Never flag generic dates, times, or timestamps — only flag dates of birth (DOB). Output only the JSON array and nothing else."
)

USER_PROMPT_TEMPLATE = """Find all proper nouns, personal data and sensitive identifiers in the TEXT below.

Include:
- Personal names from any culture or language — including Asian, Arabic, Eastern European and other non-Western names (NAME)
- Email addresses (EMAIL)
- Phone numbers in any format (PHONE)
- Street addresses, postcodes (ADDRESS)
- Company / organisation / brand names (COMPANY)
- URLs and domain names (URL)
- ID numbers: SSN, PESEL, NIP, passport number (SSN)
- Usernames, login names, handles (USERNAME)
- Dates of birth, birth dates — NOT generic dates or timestamps (DOB)
- IBANs, bank account numbers, credit card numbers (FINANCE)
- IP addresses (IPv4 / IPv6), MAC addresses (IP_ADDRESS)
- Geographic coordinates, latitude/longitude pairs (COORDINATES)
- Project / WBS codes (WBS_CODE)
- Any other sensitive identifier (OTHER_PII)

Do NOT include: generic dates, times, timestamps (e.g. "12 March 2025", "14:30", "Q1 2024"), standalone city or country names.

Example input: "Hi, I'm Sarah Connor. Call me at +1-800-555-0199 or sarah@sky.net. I work at Cyberdyne Systems, 18144 El Camino Real."
Example output: [{{"value":"Sarah Connor","type":"NAME"}},{{"value":"+1-800-555-0199","type":"PHONE"}},{{"value":"sarah@sky.net","type":"EMAIL"}},{{"value":"Cyberdyne Systems","type":"COMPANY"}},{{"value":"18144 El Camino Real","type":"ADDRESS"}}]

Example input: "Please contact Yuki Sato at yuki.sato@corp.jp or Mohammed Al-Rashid at +971-50-123-4567."
Example output: [{{"value":"Yuki Sato","type":"NAME"}},{{"value":"yuki.sato@corp.jp","type":"EMAIL"}},{{"value":"Mohammed Al-Rashid","type":"NAME"}},{{"value":"+971-50-123-4567","type":"PHONE"}}]

TEXT:
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
        "options": {"temperature": 0},
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
    Replace original values with placeholders in a single pass.
    replacements: { "[NAME_1]": "Jane Doe", ... }
    Longest original first so partial-match collisions can't occur.
    """
    if not replacements:
        return text
    # Invert: original → placeholder, sorted longest-original-first
    pairs = sorted(
        ((original, placeholder) for placeholder, original in replacements.items()),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    pattern = re.compile('|'.join(re.escape(orig) for orig, _ in pairs))
    lookup = {orig: ph for orig, ph in pairs}
    return pattern.sub(lambda m: lookup[m.group(0)], text)


def restore_replacements(text: str, replacements: dict[str, str]) -> tuple[str, list[dict]]:
    """
    Replace placeholders with original values in a single pass.
    replacements: { "[NAME_1]": "Jane Doe", ... }
    Returns (restored_text, highlighted_ranges) where each range is
    {"start": int, "end": int, "fake": str, "original": str}.

    Single-pass via re.finditer so every position is visited exactly once —
    no cascading replacements and all range offsets are relative to the
    final output string (not an intermediate mutation).
    """
    if not replacements:
        return text, []

    pairs = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
    pattern = re.compile('|'.join(re.escape(ph) for ph, _ in pairs))

    result: list[str] = []
    ranges: list[dict] = []
    out_pos = 0
    prev_end = 0

    for m in pattern.finditer(text):
        segment = text[prev_end:m.start()]
        result.append(segment)
        out_pos += len(segment)

        placeholder = m.group(0)
        original = replacements[placeholder]
        result.append(original)
        ranges.append({
            "start": out_pos,
            "end": out_pos + len(original),
            "fake": placeholder,
            "original": original,
        })
        out_pos += len(original)
        prev_end = m.end()

    result.append(text[prev_end:])
    return ''.join(result), ranges
