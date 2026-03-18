# CLAUDE.md — PII Anonymiser

Local POC single-page web application. Anonymises user prompts via a local LLM (phi3:mini)
before sending them to Claude Haiku, then de-anonymises the response programmatically.

---

## Project overview

```
User input ──► phi3:mini (Ollama, local) ──► entity detection
                                               │
                              backend replaces entities with placeholders
                                               │
                              user reviews & edits anonymised text
                                               │
                                       Claude Haiku API
                                               │
                              backend replaces placeholders with originals
                                               │
                              highlighted de-anonymised response ──► user
```

**PII entity types detected:** NAME · EMAIL · ADDRESS · COMPANY · PHONE · SSN · WBS_CODE · OTHER_PII

---

## Architecture

| Layer | Technology | Notes |
|-------|-----------|-------|
| Anonymiser LLM | phi3:mini via Ollama | Runs locally on Apple Silicon |
| Backend API | Python 3.11 + FastAPI | Served on localhost:8000 |
| Frontend | Vanilla HTML/CSS/JS SPA | Single `index.html`, no framework |
| External LLM | Claude Haiku (`claude-haiku-4-5`) | Anthropic API |
| API key storage | `.env` file (project root) | Never exposed externally |

**Target hardware:** MacBook Air M2 (MW103ZE/A) — all components run locally.

---

## File structure

```
├── app/
│   ├── main.py             FastAPI app: serves static files + API routes
│   ├── anonymiser.py       phi3:mini via Ollama — entity detection only
│   ├── claude_client.py    Claude Haiku API call
│   ├── session_store.py    In-memory session store (session_id → mapping)
│   ├── config.py           Loads ANTHROPIC_API_KEY from .env
│   ├── requirements.txt
│   └── static/
│       └── index.html      Single-page UI (3-view JS state machine)
├── .env                    ANTHROPIC_API_KEY=sk-ant-...  ← git-ignored
├── .gitignore
├── start.sh                Launch script
└── CLAUDE.md               This file
```

---

## API design

| Method | Path | Request body | Response |
|--------|------|-------------|---------|
| `POST` | `/api/session` | `{}` | `{ session_id }` |
| `POST` | `/api/anonymise` | `{ session_id, text }` | `{ anonymised_text, entities: [{placeholder, original, type}] }` |
| `POST` | `/api/anonymise/update` | `{ session_id, action, placeholder?, original?, text? }` | `{ anonymised_text, entities }` |
| `POST` | `/api/complete` | `{ session_id, anonymised_text }` | `{ response_text, entities, highlighted_ranges }` |

### Session & mapping
- Sessions are **in-memory only** — lost on server restart or browser refresh (acceptable for POC).
- Session TTL: 2 hours.
- Mapping format: `{ "[NAME_1]": "Jane Doe", "[EMAIL_1]": "jane@acme.com" }`
- Placeholder format: `[TYPE_N]` where N increments per type per session (e.g. `[NAME_1]`, `[NAME_2]`).
- Same original value always gets the same placeholder within a session.
- Entities sorted longest-first before replacement to avoid partial-match collisions.

### `/api/anonymise/update` actions
- `add` — user manually highlights text and provides a free-form custom placeholder.
  - Body: `{ session_id, action: "add", original: "highlighted text", placeholder: "[CUSTOM_LABEL]", text: "current anonymised text" }`
- `remove` — user removes an entity from the mapping and restores original text.
  - Body: `{ session_id, action: "remove", placeholder: "[NAME_1]", text: "current anonymised text" }`

### De-anonymisation
Done **programmatically** by the backend (no LLM involved):
```python
for placeholder, original in mapping.items():
    response_text = response_text.replace(placeholder, original)
```
The backend also returns character ranges of restored values for frontend highlighting.

---

## phi3:mini integration (anonymiser.py)

- Calls Ollama at `http://localhost:11434/api/generate`
- Uses `format: "json"` to force structured output
- Prompt instructs the model to return a JSON array of detected entities:
  ```json
  [{"value": "Jane Doe", "type": "NAME"}, {"value": "jane@acme.com", "type": "EMAIL"}]
  ```
- The backend (not the model) performs the actual text replacement.
- If Ollama is unreachable, return "please ensure Ollama is running on your device. Run terminal command: " .
- Model: `phi3:mini` (assumed already pulled — `ollama pull phi3:mini`)

---

## Claude Haiku integration (claude_client.py)

- Model ID: `claude-haiku-4-5`
- Uses `anthropic` Python SDK
- System prompt: instruct the model to respond helpfully; placeholders like `[NAME_1]` in the
  prompt are intentional anonymisation tokens — do not modify or expand them.
- API key loaded from `.env` via `config.py` — never hardcoded, never logged.

---

## Frontend (index.html)

Single file. Three views managed by a JS state machine (no page reload, no framework).

### Design reference
- **Style base:** `style.css` in project root (Fujitsu destyle CSS reset — link it from index.html)
- **Reference image:** `examplewebpage.png` (Fujitsu corporate look: white background, red CTAs, clean typography)
- **Font stack:** `FujitsuInfinityPro, Arial, sans-serif` (FujitsuInfinityPro will not load locally — Arial fallback is fine)
- **Colour palette:**
  - Primary action (buttons): `#E4002B` (Fujitsu red)
  - Anonymised placeholder highlights: `#FFF3CD` background, `#856404` text (amber)
  - De-anonymised value highlights: `#D4EDDA` background, `#155724` text (green)
  - Neutral background: `#F8F9FA`
  - Card background: `#FFFFFF` with subtle `box-shadow`

> **IMPORTANT:** Before generating any frontend code, invoke the `frontend-design` skill.

### View 1 — Input
- Full-width `<textarea>` placeholder: "Paste your prompt here…"
- "Anonymise" button (primary, red) → POST `/api/session` then POST `/api/anonymise`
- Loading spinner overlay while phi3:mini processes

### View 2 — Review (side-by-side)
- Left panel: original text (read-only, light grey background)
- Right panel: anonymised text — placeholders rendered as amber `<mark>` chips, editable otherwise
- If no entities detected: show a blue info banner "No PII detected. You may still add anonymisations manually."
- Entity table below both panels:
  | Placeholder | Original value | Remove |
  - "Remove" button calls `/api/anonymise/update` with action `remove`
- Text-selection interaction on the right panel:
  - On `mouseup`, if text is selected, show a floating "Add anonymisation" button near selection
  - Clicking it opens a small modal: input field pre-filled with `[CUSTOM]`, user edits freely
  - On confirm → POST `/api/anonymise/update` with action `add`
- "Prompt external model →" button (primary) → View 3

### View 3 — Response
- Response text rendered with de-anonymised values wrapped in green `<mark>` elements
- Hovering a green mark shows a tooltip with the placeholder that was used (e.g. `[NAME_1]`)
- PII summary table below:
  | Placeholder | Original value |
- "Start over" button → clears session state, returns to View 1

---

## Configuration

### `.env` (git-ignored)
```
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```

### `config.py`
```python
from dotenv import load_dotenv
import os

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
```

---

## Prerequisites (already on user's machine)
- Python 3.11+
- Ollama installed and running (`ollama serve`)
- phi3:mini pulled (`ollama pull phi3:mini`)
- `.env` file created with Anthropic API key

---

## Start script (start.sh)

```bash
#!/usr/bin/env bash
set -e

# Ensure Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve &
  sleep 2
fi

cd app
source ../.venv/bin/activate 2>/dev/null || python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -q -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Run: `chmod +x start.sh && ./start.sh`
Open: `http://localhost:8000`

---

## Known limitations (POC scope)

- **Single user** — in-memory store, not designed for concurrent sessions.
- **In-memory only** — refreshing the browser loses the session and mapping.
- **phi3:mini accuracy** — small model; always review the entity table before sending.
- **HTTP only** — runs on localhost, no TLS needed.
- **Manual edits not back-tracked** — if you type a placeholder directly into the text area that
  isn't in the session mapping, de-anonymisation will leave it unreplaced.
- **Free-form custom placeholders** — must be unique; duplicates overwrite the mapping entry.

---

## Key constraints

- Do **not** log or persist PII anywhere (no files, no database, no stdout logging of entity values).
- Do **not** expose the Anthropic API key in any frontend code or API response.
- Keep all LLM calls to phi3:mini **local only** (Ollama on localhost).
- Session IDs should be random UUIDs (use `uuid.uuid4()`).
