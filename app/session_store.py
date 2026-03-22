import time
import threading
from typing import Optional

SESSION_TTL = 2 * 60 * 60  # 2 hours in seconds

# Each session: { "mapping": {placeholder: original}, "types": {placeholder: entity_type},
#                 "fakes": set(), "counters": {type: int},
#                 "conversation_history": [{role, content}, ...], "created_at": float }
_store: dict[str, dict] = {}
_lock = threading.Lock()


def _next_placeholder(session: dict, entity_type: str) -> str:
    """Generate the next sequential placeholder for a given entity type, e.g. [NAME_1]."""
    counters = session["counters"]
    counters[entity_type] = counters.get(entity_type, 0) + 1
    placeholder = f"[{entity_type}_{counters[entity_type]}]"
    session["fakes"].add(placeholder)
    return placeholder


def create_session(session_id: str) -> None:
    with _lock:
        _store[session_id] = {
            "mapping": {},
            "types": {},
            "fakes": set(),
            "counters": {},
            "conversation_history": [],
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


def get_or_create_fake(session_id: str, original: str, entity_type: str) -> str:
    """Return existing placeholder for this value or generate a new one."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")

    with _lock:
        mapping = session["mapping"]
        # Return existing placeholder if we've seen this value before
        for placeholder, value in mapping.items():
            if value == original:
                return placeholder

        placeholder = _next_placeholder(session, entity_type)
        mapping[placeholder] = original
        session["types"][placeholder] = entity_type
        return placeholder


def add_custom_fake(session_id: str, original: str, fake: str) -> str:
    """Add a user-defined mapping entry.

    The user-supplied label is wrapped in [...] brackets so it is treated as
    an opaque placeholder token (like [NAME_1]) rather than real-looking text
    that Claude might modify during rewriting. If the user already typed brackets
    they are not doubled.
    """
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    placeholder = fake if (fake.startswith("[") and fake.endswith("]")) else f"[{fake}]"
    with _lock:
        session["mapping"][placeholder] = original
        session["types"][placeholder] = "CUSTOM"
        session["fakes"].add(placeholder)
    return placeholder


def remove_fake(session_id: str, fake: str) -> Optional[str]:
    """Remove a mapping entry; return the original value or None if not found."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    with _lock:
        session["fakes"].discard(fake)
        session["types"].pop(fake, None)
        return session["mapping"].pop(fake, None)


def append_to_history(session_id: str, role: str, content: str) -> None:
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    with _lock:
        session["conversation_history"].append({"role": role, "content": content})


def get_history(session_id: str) -> list[dict]:
    session = get_session(session_id)
    return list(session["conversation_history"]) if session else []


def list_entities(session_id: str) -> list[dict]:
    """Return list of {fake, original, type} dicts."""
    session = get_session(session_id)
    if session is None:
        return []
    types = session["types"]
    return [
        {"fake": k, "original": v, "type": types.get(k, "OTHER_PII")}
        for k, v in session["mapping"].items()
    ]
