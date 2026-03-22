import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from aws_xray_sdk.core import xray_recorder, patch
from starlette.middleware.base import BaseHTTPMiddleware

import session_store
import anonymiser as anon
import claude_client

app = FastAPI(title="Chat Anonymiser")

xray_recorder.configure(
    service="chat-anonymiser",
    context_missing="LOG_ERROR",
)
patch(["boto3"])


class _XRayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        xray_recorder.begin_segment(f"{request.method} {request.url.path}")
        try:
            return await call_next(request)
        finally:
            xray_recorder.end_segment()


app.add_middleware(_XRayMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure all unhandled exceptions return JSON rather than plain-text 500."""
    return JSONResponse(status_code=500, content={"detail": str(exc)})

STATIC_DIR = Path(__file__).parent / "static"
ROOT_DIR = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/style.css")
async def serve_css():
    return FileResponse(ROOT_DIR / "style.css", media_type="text/css")


# ── Models ────────────────────────────────────────────────────────────────────

class SessionResponse(BaseModel):
    session_id: str


class AnonymiseRequest(BaseModel):
    session_id: str
    text: str


class AnonymiseResponse(BaseModel):
    anonymised_text: str
    entities: list[dict]  # [{fake, original}]


class UpdateRequest(BaseModel):
    session_id: str
    action: str          # "add" | "remove"
    fake: str | None = None
    original: str | None = None
    text: str            # current anonymised text


class CompleteRequest(BaseModel):
    session_id: str
    anonymised_text: str


class CompleteResponse(BaseModel):
    response_text: str
    entities: list[dict]           # [{fake, original}]
    highlighted_ranges: list[dict] # [{start, end, fake, original}]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/session", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    session_store.create_session(session_id)
    return SessionResponse(session_id=session_id)


@app.post("/api/anonymise", response_model=AnonymiseResponse)
async def anonymise(req: AnonymiseRequest):
    if session_store.get_session(req.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        entities = await anon.detect_entities(req.text)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "please ensure Ollama is running on your device. "
                "Run terminal command: ollama serve"
            ),
        )

    # Register each entity with the session and build replacements
    for entity in entities:
        session_store.get_or_create_fake(
            req.session_id, entity["value"], entity["type"]
        )

    mapping = session_store.get_mapping(req.session_id)
    anonymised_text = anon.apply_replacements(req.text, mapping)

    return AnonymiseResponse(
        anonymised_text=anonymised_text,
        entities=session_store.list_entities(req.session_id),
    )


@app.post("/api/anonymise/update", response_model=AnonymiseResponse)
async def anonymise_update(req: UpdateRequest):
    if session_store.get_session(req.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if req.action == "add":
        if not req.original or not req.fake:
            raise HTTPException(status_code=422, detail="'original' and 'fake' required for add")
        wrapped_fake = session_store.add_custom_fake(req.session_id, req.original, req.fake)
        # Apply only the new entry to the current text (original → wrapped fake)
        updated_text = req.text.replace(req.original, wrapped_fake)

    elif req.action == "remove":
        if not req.fake:
            raise HTTPException(status_code=422, detail="'fake' required for remove")
        original = session_store.remove_fake(req.session_id, req.fake)
        if original is None:
            raise HTTPException(status_code=404, detail="Fake value not found in session")
        # Restore the fake back to original value in current text
        updated_text = req.text.replace(req.fake, original)

    else:
        raise HTTPException(status_code=422, detail=f"Unknown action '{req.action}'")

    return AnonymiseResponse(
        anonymised_text=updated_text,
        entities=session_store.list_entities(req.session_id),
    )


@app.post("/api/complete", response_model=CompleteResponse)
async def complete(req: CompleteRequest):
    if session_store.get_session(req.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    history = session_store.get_history(req.session_id)
    messages = history + [{"role": "user", "content": req.anonymised_text}]

    try:
        raw_response = await claude_client.complete(messages)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    session_store.append_to_history(req.session_id, "user", req.anonymised_text)
    session_store.append_to_history(req.session_id, "assistant", raw_response)

    mapping = session_store.get_mapping(req.session_id)
    response_text, highlighted_ranges = anon.restore_replacements(raw_response, mapping)

    return CompleteResponse(
        response_text=response_text,
        entities=session_store.list_entities(req.session_id),
        highlighted_ranges=highlighted_ranges,
    )
