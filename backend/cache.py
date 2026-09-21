"""
cache.py — a plain in-process TTL cache.

The old version imported `fakeredis` and called it Redis, which was
misleading (it's not shared across workers, not persistent, and wasn't even
in requirements.txt). This is exactly as "real" as that was — in-process
only — just honest about it. If you outgrow a single worker process later,
swap this file for a real `redis` client; nothing else in the codebase
needs to change since it only calls get/set/delete.
"""
import time

_store: dict[str, tuple[float, object]] = {}  # key -> (expires_at, value)


def get_cached(key: str):
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _store.pop(key, None)
        return None
    return value


def set_cached(key: str, value, ttl_seconds: int = 60):
    _store[key] = (time.time() + ttl_seconds, value)


def delete_cached(key: str):
    _store.pop(key, None)
