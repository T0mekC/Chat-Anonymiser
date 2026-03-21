"""
Sends the anonymised prompt to Claude Haiku and returns the raw response text.
De-anonymisation is handled by the caller (main.py) using anonymiser.restore_replacements().
"""

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "The user's message may contain anonymisation placeholders wrapped in square brackets, "
    "for example [NAME_1], [EMAIL_2], [COMPANY_1], or descriptive labels like [bank phone], [customer email]. "
    "These tokens stand in for real names, organisations, and other sensitive values. "
    "You MUST copy every placeholder into your response exactly as it appears — "
    "never expand, replace, paraphrase, split, or omit them. "
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
