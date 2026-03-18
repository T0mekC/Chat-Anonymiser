import time
import threading
from typing import Optional

SESSION_TTL = 2 * 60 * 60  # 2 hours in seconds

# Each session: { "mapping": {"[NAME_1]": "Jane Doe", ...}, "counters": {"NAME": 1, ...}, "created_at": float }
_store: dict[str, dict] = {}
_lock = threading.Lock()


def create_session(session_id: str) -> None:
    with _lock:
        _store[session_id] = {
            "mapping": {},
            "counters": {},
            "created_at": time.time(),
        }


def get_session(session_id: str) -> Optional[dict]:
    with _lock:
        session = _store.get(session_id)
        if session is None:
            return None
        if time.time() - session["created_at"] > SESSION_TTL:
            del _store[session_id]
            return None
        return session


def get_mapping(session_id: str) -> Optional[dict[str, str]]:
    session = get_session(session_id)
    return session["mapping"] if session else None


def get_or_create_placeholder(session_id: str, original: str, entity_type: str) -> str:
    """Return existing placeholder for this value or create a new one."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")

    with _lock:
        mapping = session["mapping"]
        # Return existing placeholder if we've seen this value before
        for placeholder, value in mapping.items():
            if value == original:
                return placeholder

        # Allocate the next counter for this type
        counters = session["counters"]
        n = counters.get(entity_type, 0) + 1
        counters[entity_type] = n
        placeholder = f"[{entity_type}_{n}]"
        mapping[placeholder] = original
        return placeholder


def add_custom_placeholder(session_id: str, original: str, placeholder: str) -> None:
    """Add a user-defined mapping entry (free-form placeholder)."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    with _lock:
        session["mapping"][placeholder] = original


def remove_placeholder(session_id: str, placeholder: str) -> Optional[str]:
    """Remove a mapping entry; return the original value or None if not found."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    with _lock:
        return session["mapping"].pop(placeholder, None)


def list_entities(session_id: str) -> list[dict]:
    """Return sorted list of {placeholder, original} dicts."""
    mapping = get_mapping(session_id)
    if mapping is None:
        return []
    return [{"placeholder": k, "original": v} for k, v in mapping.items()]
