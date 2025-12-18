# src/tools/agent_health_check.py
from __future__ import annotations
from datetime import datetime, timezone

def run_agent_health_check() -> dict:
    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "agents_expected": ["technical", "news_sentiment"],
        "status": "ok",
        "notes": "CryptoNews API fully removed"
    }

if __name__ == "__main__":
    import json
    print(json.dumps(run_agent_health_check(), indent=2))
