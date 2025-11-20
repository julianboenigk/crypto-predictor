# src/core/llm.py
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from openai import OpenAI  # type: ignore

_client: Optional[OpenAI] = None

# Files für Logging und Tages-State
LLM_USAGE_FILE = Path("data/llm_usage.jsonl")
LLM_DAILY_STATE_FILE = Path("data/llm_daily_state.json")
LLM_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
LLM_DAILY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_client() -> OpenAI:
    """
    Singleton OpenAI Client.
    """
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _log_usage(model: str, usage: Any, context: str) -> None:
    """
    usage: resp.usage-Objekt aus OpenAI Rückgabe.
    context: z. B. 'research', 'meta_explain', 'self_eval', ...
    """
    try:
        rec = {
            "t": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "context": context,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
        with LLM_USAGE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        # Logging darf NIE Fehler werfen
        pass


def _get_daily_limits() -> tuple[int, int]:
    """
    Lies tägliche Limits aus ENV.

    MAX_LLM_TOKENS_PER_DAY: maximale Token-Anzahl pro Tag (<=0 = kein Limit)
    MAX_LLM_CALLS_PER_DAY: maximale Anzahl Calls pro Tag (<=0 = kein Limit)
    """
    try:
        max_tokens = int(os.getenv("MAX_LLM_TOKENS_PER_DAY", "0"))
    except ValueError:
        max_tokens = 0
    try:
        max_calls = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "0"))
    except ValueError:
        max_calls = 0
    return max_tokens, max_calls


def _load_daily_state() -> Dict[str, Any]:
    """
    Lade den Tages-State (Date, tokens_used, calls).
    Beim Datumswechsel wird automatisch zurückgesetzt.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    if not LLM_DAILY_STATE_FILE.exists():
        return {"date": today, "tokens_used": 0, "calls": 0}

    try:
        raw = json.loads(LLM_DAILY_STATE_FILE.read_text(encoding="utf-8"))
        if raw.get("date") != today:
            # Neues Datum: State zurücksetzen
            return {"date": today, "tokens_used": 0, "calls": 0}
        return {
            "date": raw.get("date", today),
            "tokens_used": int(raw.get("tokens_used", 0)),
            "calls": int(raw.get("calls", 0)),
        }
    except Exception:
        # Bei Fehlern defensiv neu starten
        return {"date": today, "tokens_used": 0, "calls": 0}


def _save_daily_state(state: Dict[str, Any]) -> None:
    try:
        LLM_DAILY_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        # Darf den Lauf nicht stören
        pass


def _check_llm_limit(context: str) -> bool:
    """
    Prüft, ob ein weiterer LLM-Call heute noch erlaubt ist.

    Rückgabe:
    - True: Call ist erlaubt
    - False: Limit überschritten, Call sollte NICHT mehr erfolgen
    """
    max_tokens, max_calls = _get_daily_limits()
    state = _load_daily_state()

    # Wenn keine Limits gesetzt sind, ist alles erlaubt
    if max_tokens <= 0 and max_calls <= 0:
        return True

    tokens_ok = True
    calls_ok = True

    if max_tokens > 0 and state["tokens_used"] >= max_tokens:
        tokens_ok = False
    if max_calls > 0 and state["calls"] >= max_calls:
        calls_ok = False

    if not (tokens_ok and calls_ok):
        # Optional könnte man hier noch in eine Log-Datei schreiben, dass Limit erreicht ist.
        return False

    return True


def _update_llm_state_after_call(usage: Any) -> None:
    """
    Aktualisiere den Tages-State nach einem erfolgreichen LLM-Call.
    """
    total_tokens = getattr(usage, "total_tokens", None)
    try:
        total_tokens_int = int(total_tokens) if total_tokens is not None else 0
    except Exception:
        total_tokens_int = 0

    state = _load_daily_state()
    state["tokens_used"] = int(state.get("tokens_used", 0)) + total_tokens_int
    state["calls"] = int(state.get("calls", 0)) + 1
    _save_daily_state(state)


def simple_completion(
    system_prompt: str,
    user_prompt: str,
    model_env_var: str = "OPENAI_MODEL",
    default_model: str = "gpt-4.1-mini",
    max_tokens: int = 600,
    temperature: float = 0.3,
    context: str = "generic",
) -> str:
    """
    Wrapper für Chat Completions.
    Unterstützt GPT-4.x/GPT-5.x (nur max_completion_tokens).
    Fügt Usage-Logging und tägliche Limits hinzu.
    """
    # Zuerst Limits prüfen
    if not _check_llm_limit(context=context):
        # Wenn Limit erreicht, lieber einen klaren Hinweis zurückgeben
        return f"[LLM-Limit für heute erreicht im Kontext '{context}']"

    client = get_client()
    model = os.getenv(model_env_var, default_model)

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }

    resp = client.chat.completions.create(**kwargs)

    # Usage Logging + State-Update
    try:
        if hasattr(resp, "usage") and resp.usage is not None:
            _log_usage(model, resp.usage, context=context)
            _update_llm_state_after_call(resp.usage)
    except Exception:
        pass

    # Saubere Rückgabe
    try:
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""
