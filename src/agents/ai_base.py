from __future__ import annotations
from src.bootstrap.env import env_debug  # noqa: F401

# ============================================================
# VERY EARLY ENV LOADING (before anything else)
# ============================================================
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

# ============================================================
# Standard imports
# ============================================================
import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

# ============================================================
# OpenAI Client (SDK >=1.0)
# ============================================================
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("[AI_BASE] WARNING: OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# Limits (0 = disabled)
# ============================================================
def _int_env(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default

MAX_LLM_CALLS_PER_DAY = _int_env("MAX_LLM_CALLS_PER_DAY", 0)
MAX_LLM_TOKENS_PER_DAY = _int_env("MAX_LLM_TOKENS_PER_DAY", 0)

OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL_DEFAULT", "gpt-4.1-mini")

# ============================================================
# Utility
# ============================================================
def deterministic_hash(data: Any) -> str:
    try:
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    except Exception:
        encoded = str(data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

# ============================================================
# Cache
# ============================================================
def cache_path(agent_name: str, key: str) -> Path:
    path = PROJECT_ROOT / "data" / "agent_cache" / agent_name
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{key}.json"


def load_cache(agent_name: str, key: str) -> Optional[Dict[str, Any]]:
    path = cache_path(agent_name, key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cache(agent_name: str, key: str, data: Dict[str, Any]) -> None:
    path = cache_path(agent_name, key)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

# ============================================================
# LLM Usage Tracking
# ============================================================
USAGE_PATH = PROJECT_ROOT / "data" / "llm_usage.json"

def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def load_llm_usage() -> Tuple[int, int]:
    if not USAGE_PATH.exists():
        return 0, 0
    try:
        data = json.loads(USAGE_PATH.read_text())
        today = data.get(_today(), {})
        return int(today.get("calls", 0)), int(today.get("tokens", 0))
    except Exception:
        return 0, 0


def save_llm_usage(calls: int, tokens: int) -> None:
    data = {}
    if USAGE_PATH.exists():
        try:
            data = json.loads(USAGE_PATH.read_text())
        except Exception:
            pass

    data[_today()] = {"calls": calls, "tokens": tokens}
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USAGE_PATH.write_text(json.dumps(data, indent=2))

# ============================================================
# Limit Check (clean & explicit)
# ============================================================
def check_limits(tokens_required: int = 0) -> Tuple[bool, str]:
    calls, tokens_used = load_llm_usage()

    if MAX_LLM_CALLS_PER_DAY > 0 and calls >= MAX_LLM_CALLS_PER_DAY:
        return False, "MAX_CALLS_REACHED"

    if MAX_LLM_TOKENS_PER_DAY > 0 and (tokens_used + tokens_required) > MAX_LLM_TOKENS_PER_DAY:
        return False, "MAX_TOKENS_REACHED"

    return True, ""

# ============================================================
# Prompt Loader
# ============================================================
def load_prompt(prompt_file: str) -> str:
    path = PROJECT_ROOT / "prompts" / prompt_file
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return "SCORE: 0\nCONFIDENCE: 0"

# ============================================================
# LLM Call
# ============================================================
def run_llm(prompt: str, model: str = OPENAI_MODEL_DEFAULT) -> Dict[str, Any]:
    token_estimate = max(1, len(prompt.split()))

    allowed, reason = check_limits(token_estimate)
    if not allowed:
        print(f"[AI_BASE] LLM blocked: {reason}")
        return {
            "raw_output": "LIMIT_REACHED",
            "limit_reason": reason,
        }

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=128,
    )

    raw = response.choices[0].message.content or ""

    calls, tokens_used = load_llm_usage()
    save_llm_usage(
        calls + 1,
        tokens_used + (response.usage.total_tokens or 0),
    )

    return {
        "raw_output": raw,
        "response": response,
    }

# ============================================================
# Dataclass
# ============================================================
@dataclass
class AgentOutput:
    agent: str
    score: float
    confidence: float
    raw: Dict[str, Any]

# ============================================================
# Base Agent
# ============================================================
class AIAgent:
    agent_name: str = "ai_base"
    prompt_file: str = "prompt_not_set.txt"
    model_name: str = OPENAI_MODEL_DEFAULT

    def build_prompt(self, candle_window: Any, external_data: Dict[str, Any]) -> str:
        template = load_prompt(self.prompt_file)
        return template.format(
            candles=json.dumps(candle_window, ensure_ascii=False),
            data=json.dumps(external_data, ensure_ascii=False),
        )

    def run(self, candle_window: Any, external_data: Dict[str, Any]) -> AgentOutput:
        key = deterministic_hash({"c": candle_window, "e": external_data})

        cached = load_cache(self.agent_name, key)
        if cached:
            return AgentOutput(
                self.agent_name,
                cached["score"],
                cached["confidence"],
                cached["raw"],
            )

        prompt = self.build_prompt(candle_window, external_data)
        out = run_llm(prompt, model=self.model_name)

        score, conf = self.parse_output(out.get("raw_output", ""))

        result = {
            "score": score,
            "confidence": conf,
            "raw": out,
        }
        save_cache(self.agent_name, key, result)

        return AgentOutput(self.agent_name, score, conf, out)

    @staticmethod
    def parse_output(text: str) -> Tuple[float, float]:
        if not text or "LIMIT_REACHED" in text:
            return 0.0, 0.0

        score = 0.0
        conf = 0.0
        for line in text.splitlines():
            if line.upper().startswith("SCORE:"):
                score = float(line.split(":", 1)[1].strip())
            elif line.upper().startswith("CONFIDENCE:"):
                conf = float(line.split(":", 1)[1].strip())
        return score, conf
