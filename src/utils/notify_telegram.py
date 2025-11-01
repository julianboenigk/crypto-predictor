# src/utils/notify_telegram.py
from __future__ import annotations
import os
import json
import time
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # optional dependency

def _load_env_once() -> None:
    """Load .env from repo root (../.. from this file)."""
    if getattr(_load_env_once, "_did", False):
        return
    _load_env_once._did = True  # type: ignore[attr-defined]

    if load_dotenv is None:
        return
    here = Path(__file__).resolve()
    repo_root = here.parents[2]  # .../src/utils -> .../src -> <repo>
    env_path = repo_root / ".env"
    load_dotenv(dotenv_path=str(env_path), override=False)

def _env_bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")

def _get_token() -> str:
    # Primary: TELEGRAM_TOKEN; Fallback: TELEGRAM_BOT_TOKEN
    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    return token.strip()

def _get_chat_id() -> str:
    return (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

def _enabled() -> bool:
    # Default enabled unless explicitly set to false/0
    return _env_bool("TELEGRAM_ENABLED", True)

def _check_env() -> None:
    _load_env_once()
    if not _enabled():
        raise RuntimeError("Telegram disabled (TELEGRAM_ENABLED is false).")
    if not _get_token():
        raise RuntimeError("TELEGRAM_TOKEN (or TELEGRAM_BOT_TOKEN) not set in environment/.env")
    if not _get_chat_id():
        raise RuntimeError("TELEGRAM_CHAT_ID not set in environment/.env")

def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_get_token()}/{method}"

def send_message(text: str, parse_mode: Optional[str] = None) -> bool:
    """Send one Telegram message. Returns True on success, False otherwise."""
    _load_env_once()
    if not _enabled():
        # Silently succeed when disabled so callers don't error
        return True

    import requests
    try:
        _check_env()
    except RuntimeError as e:
        print(f"Telegram not ready: {e}", flush=True)
        return False

    payload = {"chat_id": _get_chat_id(), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(_api_url("sendMessage"), json=payload, timeout=15)
        if r.status_code != 200:
            print(f"Telegram HTTP {r.status_code}: {r.text}", flush=True)
            return False
        data = r.json()
        if not data.get("ok"):
            print(f"Telegram error: {json.dumps(data)}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"Telegram exception: {e}", flush=True)
        return False

def send_alert(title: str, bullets: Iterable[str], chunk: int = 8) -> bool:
    """Headline + bullets, split across messages if needed."""
    if not _enabled():
        return True
    header = f"*{title}*"
    ok = send_message(header, parse_mode="Markdown")
    if not ok:
        return False

    lines: List[str] = list(bullets)
    for i in range(0, len(lines), chunk):
        body = "\n".join(f"• {ln}" for ln in lines[i : i + chunk])
        ok = send_message(body, parse_mode="Markdown")
        if not ok:
            return False
        time.sleep(0.4)
    return True
