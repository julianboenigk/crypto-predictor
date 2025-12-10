from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

# ============================================================
# Load .env EARLY
# ============================================================
import pathlib
from dotenv import load_dotenv

ENV_PATH = pathlib.Path("/home/crypto/crypto-predictor/.env")
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    print(f"[AI_BASE] WARNING: .env not found at {ENV_PATH}")

# ============================================================
# OpenAI Client (new API, required for openai>=1.0)
# ============================================================
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# Limits
# ============================================================
MAX_LLM_CALLS_PER_DAY = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "1000"))
MAX_LLM_TOKENS_PER_DAY = int(os.getenv("MAX_LLM_TOKENS_PER_DAY", "400000"))
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL_DEFAULT", "gpt-4.1-mini")

# ============================================================
# Utility: deterministic hashing
# ============================================================
def deterministic_hash(data: Any) -> str:
    try:
        encoded = json.dumps(data, sort_keys=True).encode("utf-8")
    except Exception:
        encoded = str(data).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

# ============================================================
# Cache Management
# ============================================================
def cache_path(agent_name: str, key: str) -> str:
    directory = f"data/agent_cache/{agent_name}"
    os.makedirs(directory, exist_ok=True)
    return f"{directory}/{key}.json"


def load_cache(agent_name: str, key: str) -> Optional[Dict[str, Any]]:
    path = cache_path(agent_name, key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(agent_name: str, key: str, data: Dict[str, Any]) -> None:
    path = cache_path(agent_name, key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ============================================================
# LLM Usage Tracking
# ============================================================
def load_llm_usage() -> Tuple[int, int]:
    path = "data/llm_usage.json"
    if not os.path.exists(path):
        return 0, 0
    try:
        with open(path, "r") as f:
            data = json.load(f)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return data.get(today, {}).get("calls", 0), data.get(today, {}).get("tokens", 0)
    except Exception:
        return 0, 0


def save_llm_usage(calls: int, tokens: int) -> None:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    path = "data/llm_usage.json"

    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    data[today] = {"calls": calls, "tokens": tokens}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check_limits(tokens_required: int = 0) -> bool:
    calls, tokens_used = load_llm_usage()
    if calls >= MAX_LLM_CALLS_PER_DAY:
        print("[AI_BASE] max LLM calls/day exceeded")
        return False
    if tokens_used + tokens_required >= MAX_LLM_TOKENS_PER_DAY:
        print("[AI_BASE] max LLM tokens/day exceeded")
        return False
    return True

# ============================================================
# Prompt Loader
# ============================================================
def load_prompt(prompt_file: str) -> str:
    path = f"prompts/{prompt_file}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "SCORE: 0\nCONFIDENCE: 0"

# ============================================================
# NEW OpenAI LLM Call
# ============================================================
def run_llm(prompt: str, model: str = OPENAI_MODEL_DEFAULT) -> Dict[str, Any]:
    if not check_limits(tokens_required=len(prompt.split())):
        return {"raw_output": "LIMIT_REACHED", "score": 0.0, "confidence": 0.0}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=128,
        )

        raw = response.choices[0].message.content

        calls, tokens_used = load_llm_usage()
        save_llm_usage(
            calls + 1,
            tokens_used + (response.usage.total_tokens or 0)
        )

        return {"raw_output": raw, "response": response}

    except Exception as e:
        return {"raw_output": f"ERROR: {e}", "score": 0.0, "confidence": 0.0}

# ============================================================
# Dataclass
# ============================================================
@dataclass
class AgentOutput:
    agent: str
    score: float
    confidence: float
    raw: Dict[str, Any]

    def to_dict(self):
        return {
            "agent": self.agent,
            "score": self.score,
            "confidence": self.confidence,
            "raw": self.raw,
        }

# ============================================================
# Base Class
# ============================================================
class AIAgent:
    agent_name: str = "ai_base"
    prompt_file: str = "prompt_not_set.txt"
    model_name: str = OPENAI_MODEL_DEFAULT

    def build_prompt(self, candle_window: Any, external_data: Dict[str, Any]) -> str:
        try:
            template = load_prompt(self.prompt_file)
            return template.format(
                candles=json.dumps(candle_window, ensure_ascii=False),
                data=json.dumps(external_data, ensure_ascii=False),
            )
        except Exception as e:
            return f"SCORE: 0\nCONFIDENCE: 0\nERROR: {e}"

    def run(self, candle_window: Any, external_data: Dict[str, Any]) -> AgentOutput:
        safe_external = external_data if isinstance(external_data, dict) else {"data": str(external_data)}
        safe_candles = candle_window if isinstance(candle_window, (list, dict)) else []

        key = deterministic_hash({"c": safe_candles, "e": safe_external})

        cached = load_cache(self.agent_name, key)
        if cached:
            return AgentOutput(self.agent_name, cached["score"], cached["confidence"], cached["raw"])

        prompt = self.build_prompt(safe_candles, safe_external)
        out = run_llm(prompt, model=self.model_name)
        score, conf = self.parse_output(out.get("raw_output", ""))

        result = {"score": score, "confidence": conf, "raw": out}
        save_cache(self.agent_name, key, result)

        return AgentOutput(self.agent_name, score, conf, out)

    @staticmethod
    def parse_output(text: str) -> Tuple[float, float]:
        if not text:
            return 0.0, 0.0
        try:
            score = 0.0
            conf = 0.0
            for line in text.splitlines():
                up = line.upper()
                if "SCORE:" in up:
                    score = float(line.split(":")[1].strip())
                if "CONFIDENCE:" in up:
                    conf = float(line.split(":")[1].strip())
            return score, conf
        except Exception:
            return 0.0, 0.0
