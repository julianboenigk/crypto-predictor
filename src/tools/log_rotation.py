# src/tools/log_rotation.py
from __future__ import annotations

import os
from typing import List


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_str_list(name: str, default: List[str]) -> List[str]:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return [x.strip() for x in v.split(",") if x.strip()]


def _should_rotate(path: str, max_bytes: int, max_lines: int) -> bool:
    if not os.path.exists(path):
        return False

    st = os.stat(path)
    if max_bytes > 0 and st.st_size > max_bytes:
        return True

    if max_lines > 0:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for i, _ in enumerate(f, start=1):
                    if i > max_lines:
                        return True
        except OSError:
            # im Zweifel nicht rotieren, wenn wir nicht lesen können
            return False

    return False


def _rotate_file(path: str, keep: int) -> None:
    """
    Rotiert path → path.1 → path.2 → ... → path.keep
    Ältestes File wird überschrieben.
    """
    if keep <= 0:
        # einfach nur leeren, ohne History
        try:
            open(path, "w").close()
        except OSError:
            pass
        return

    # bestehende Rotationen rückwärts verschieben
    for idx in range(keep, 0, -1):
        rotated = f"{path}.{idx}"
        next_rotated = f"{path}.{idx + 1}"
        if os.path.exists(rotated):
            try:
                # letztes Level ggf. überschreiben
                os.replace(rotated, next_rotated)
            except OSError:
                pass

    # aktuelles Log wird zu .1
    if os.path.exists(path):
        try:
            os.replace(path, f"{path}.1")
        except OSError:
            pass

    # neues leeres Log anlegen
    try:
        open(path, "w").close()
    except OSError:
        pass


def maybe_rotate_all_logs() -> None:
    """
    Liest Konfiguration aus der .env und rotiert die konfigurierten Logs, falls nötig.
    """
    enabled = _env_bool("LOG_ROTATE_ENABLED", False)
    if not enabled:
        return

    files = _env_str_list(
        "LOG_ROTATE_FILES",
        ["data/runs.log", "data/paper_trades_closed.jsonl"],
    )
    max_mb = _env_int("LOG_ROTATE_MAX_MB", 10)
    max_lines = _env_int("LOG_ROTATE_MAX_LINES", 50_000)
    keep = _env_int("LOG_ROTATE_KEEP", 5)

    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0

    for path in files:
        if _should_rotate(path, max_bytes=max_bytes, max_lines=max_lines):
            _rotate_file(path, keep=keep)