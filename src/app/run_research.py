# src/app/run_research.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List

from src.agents.research import ResearchAgent  # type: ignore

try:
    # wir nutzen die bestehende Universe-Logik aus main
    from src.app.main import load_universe  # type: ignore
except Exception:
    load_universe = None  # type: ignore


def _infer_assets_from_universe() -> List[str]:
    if load_universe is None:
        # Fallback: Standard-Assets
        return ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"]

    pairs, _interval, _max_age = load_universe()
    assets = []
    for p in pairs:
        p = str(p).upper()
        if p.endswith("USDT"):
            assets.append(p[:-4])
    # de-duplizieren und sortieren
    return sorted(set(assets))


def main() -> None:
    asof = datetime.now(timezone.utc)
    assets = _infer_assets_from_universe()

    ra = ResearchAgent()
    results = ra.run(assets, asof)

    summary = {
        "run_at": asof.isoformat(),
        "n_assets": len(assets),
        "assets": assets,
        "n_results": len(results),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
