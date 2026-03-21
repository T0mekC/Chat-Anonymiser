import time
import threading
from typing import Optional

from faker import Faker

SESSION_TTL = 2 * 60 * 60  # 2 hours in seconds

# Each session: { "mapping": {fake: original}, "types": {fake: entity_type}, "fakes": set(), "created_at": float }
_store: dict[str, dict] = {}
_lock = threading.Lock()

_faker = Faker()

_FAKER_GENERATORS = {
    "NAME":        lambda: _faker.name().replace(" ", ""),
    "EMAIL":       lambda: _faker.email(),
    "PHONE":       lambda: _faker.phone_number(),
    "ADDRESS":     lambda: _faker.address().replace("\n", ", "),
    "COMPANY":     lambda: _faker.company().replace(" ", ""),
    "URL":         lambda: _faker.url(),
    "SSN":         lambda: _faker.ssn(),
    "USERNAME":    lambda: _faker.user_name(),
    "DOB":         lambda: _faker.date_of_birth(minimum_age=18, maximum_age=65).strftime("%d %b %Y"),
    "FINANCE":     lambda: _faker.iban(),
    "IP_ADDRESS":  lambda: _faker.ipv4(),
    "COORDINATES": lambda: f"{_faker.latitude()}, {_faker.longitude()}",
    "OTHER_PII":   lambda: _faker.uuid4(),
}


def _generate_unique_fake(session: dict, entity_type: str) -> str:
    """Generate a Faker value that is unique within this session."""
    fakes = session["fakes"]
    generator = _FAKER_GENERATORS.get(entity_type)

    if generator is None:
        # WBS_CODE: no Faker equivalent
        base = f"PRJ-{len(fakes) + 1:04d}"
    else:
        base = generator()

    candidate = base
    attempts = 0
    while candidate in fakes and attempts < 10:
        candidate = generator() if generator else f"{base}-{attempts + 1}"
        attempts += 1

    # Last resort: append numeric suffix
    suffix = 2
    while candidate in fakes:
        candidate = f"{base}-{suffix}"
        suffix += 1

    # Wrap in structured delimiter so the external model treats it as an opaque token
    candidate = f"<fake>{candidate}</fake>"
    fakes.add(candidate)
    return candidate


def create_session(session_id: str) -> None:
    with _lock:
        _store[session_id] = {
            "mapping": {},
            "types": {},
            "fakes": set(),
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
    """Return existing fake for this value or generate a new one."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")

    with _lock:
        mapping = session["mapping"]
        # Return existing fake if we've seen this value before
        for fake, value in mapping.items():
            if value == original:
                return fake

        fake = _generate_unique_fake(session, entity_type)
        mapping[fake] = original
        session["types"][fake] = entity_type
        return fake


def add_custom_fake(session_id: str, original: str, fake: str) -> str:
    """Add a user-defined mapping entry. Returns the wrapped fake value."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    # Wrap in custom delimiter if not already wrapped
    quoted = fake if (fake.startswith("<custom>") and fake.endswith("</custom>")) else f"<custom>{fake}</custom>"
    with _lock:
        session["mapping"][quoted] = original
        session["types"][quoted] = "CUSTOM"
        session["fakes"].add(quoted)
    return quoted


def remove_fake(session_id: str, fake: str) -> Optional[str]:
    """Remove a mapping entry; return the original value or None if not found."""
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    with _lock:
        session["fakes"].discard(fake)
        session["types"].pop(fake, None)
        return session["mapping"].pop(fake, None)


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
