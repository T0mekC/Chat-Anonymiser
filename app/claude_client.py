"""
Sends the anonymised prompt to Claude Haiku and returns the raw response text.
De-anonymisation is handled by the caller (main.py) using anonymiser.restore_replacements().
"""

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "The user's message may contain tokens wrapped in <fake>...</fake> tags. "
    "These are anonymisation placeholders that stand in for real names, organisations, and other entities. "
    "You MUST copy these tokens into your response exactly as they appear — never modify, translate, paraphrase, or omit them. "
    "Respond helpfully to the request as written."
)


async def complete(anonymised_text: str) -> str:
    """
    Send anonymised_text to Claude Haiku and return the response string.
    Raises anthropic.APIError on API failures.
    """
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    message = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": anonymised_text}],
    )

    return message.content[0].text
