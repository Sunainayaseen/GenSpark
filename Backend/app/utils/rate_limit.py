"""Lightweight in-memory login-attempt limiter.

Single-process, best-effort — keyed by IP+email so one attacker can't lock out
an arbitrary victim's account just by spamming failures from elsewhere, while
still slowing down credential-stuffing against any one account from one IP.

This is intentionally not a full solution: a multi-worker/multi-instance
production deployment would need a shared store (e.g. Redis) instead of an
in-process dict, since each worker would otherwise count separately.
"""
import time
from collections import defaultdict
from threading import Lock

WINDOW_SECONDS = 15 * 60   # 15 minutes
MAX_ATTEMPTS = 8

_lock = Lock()
_attempts = defaultdict(list)  # key -> list of failure timestamps


def _prune(key, now):
    _attempts[key] = [t for t in _attempts[key] if now - t < WINDOW_SECONDS]
    if not _attempts[key]:
        _attempts.pop(key, None)


def login_key(remote_addr, email):
    return f'{remote_addr or "?"}:{(email or "").strip().lower()}'


def is_locked_out(key) -> bool:
    now = time.time()
    with _lock:
        _prune(key, now)
        return len(_attempts.get(key, [])) >= MAX_ATTEMPTS


def record_failure(key) -> None:
    now = time.time()
    with _lock:
        _prune(key, now)
        _attempts[key].append(now)


def record_success(key) -> None:
    with _lock:
        _attempts.pop(key, None)


def seconds_until_retry(key) -> int:
    now = time.time()
    with _lock:
        _prune(key, now)
        times = _attempts.get(key, [])
        if not times:
            return 0
        return max(0, int(WINDOW_SECONDS - (now - min(times))))


# --- Generic per-key limiter (payment endpoints, etc.) ---------------------
# Same in-process/best-effort model as the login limiter above. Separate store
# so callers can't collide keys with the login limiter by accident.
_generic_lock = Lock()
_generic_hits = defaultdict(list)


def hit(key, max_hits, window_seconds) -> bool:
    """Record a call under `key` and return True if it is within the allowed
    rate, False if the caller should be rejected (429)."""
    now = time.time()
    with _generic_lock:
        hits = [t for t in _generic_hits[key] if now - t < window_seconds]
        if len(hits) >= max_hits:
            _generic_hits[key] = hits
            return False
        hits.append(now)
        _generic_hits[key] = hits
        return True
