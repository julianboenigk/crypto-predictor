# src/core/llm.py
from __future__ import annotations
import os
from typing import Optional
from openai import OpenAI  # type: ignore

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def simple_completion(
    system_prompt: str,
    user_prompt: str,
    model_env_var: str = "OPENAI_MODEL",
    default_model: str = "gpt-4.1-mini",     # fallback, falls ENV nicht gesetzt
    max_tokens: int = 600,
) -> str:
    """
    Wrapper for Chat Completions.
    gpt-5.1-2025-11-13 requires: max_completion_tokens (not max_tokens).
    """
    model = os.getenv(model_env_var, default_model)
    client = get_client()

    # Wichtig: neue Parameter-Logik für GPT-5.x
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    # 5.x Modelle akzeptieren NUR max_completion_tokens
    kwargs["max_completion_tokens"] = max_tokens

    resp = client.chat.completions.create(**kwargs)

    try:
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""
