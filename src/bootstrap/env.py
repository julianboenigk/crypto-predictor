# src/bootstrap/env.py
from pathlib import Path
from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    print(f"[BOOTSTRAP] WARNING: .env not found at {ENV_PATH}")

def env_debug():
    keys = [
        "OPENAI_API_KEY",
        "MAX_LLM_TOKENS_PER_DAY",
        "MAX_LLM_CALLS_PER_DAY",
        "OPENAI_MODEL_DEFAULT",
    ]
    return {k: os.getenv(k) for k in keys}
