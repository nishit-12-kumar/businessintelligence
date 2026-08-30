import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _get_secret_key() -> str:
    """Return the Flask secret key.

    Priority:
      1. FLASK_SECRET_KEY env var (required in production).
      2. A per-machine random key persisted in `.secret_key` (local dev only).
         Created on first run; never committed (add to .gitignore).

    This ensures local dev always works without manual setup while making it
    impossible to accidentally ship the same literal key to production.
    """
    from_env = os.environ.get('FLASK_SECRET_KEY', '')
    if from_env:
        return from_env

    # Local dev path: persist a random key so sessions survive restarts.
    key_path = Path(__file__).parent / '.secret_key'
    if key_path.exists():
        key = key_path.read_text().strip()
        if key:
            return key

    # First run: generate and persist a new random key.
    key = secrets.token_hex(32)
    try:
        key_path.write_text(key)
        # Mark as sensitive (not committed) — .gitignore should list .secret_key
    except OSError:
        pass  # If we can't persist, we'll regenerate each restart (sessions won't survive)
    return key


class Config:
    # Bug #3 fix: never ship a known literal secret. Generate a random dev key
    # on first run and persist it locally. Production MUST set FLASK_SECRET_KEY.
    SECRET_KEY = _get_secret_key()
    JSON_SORT_KEYS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
