from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

TRADES_DIR = Path("data/")
DAILY_STATE = Path("data/trading_daily_state.json")
RUNS_LOG = Path("data/runs.log")
ERRORS_LOG = Path("data/errors.log")


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # kaputte Zeilen ignorieren
                pass
    return out


def load_paper_trades() -> List[Dict[str, Any]]:
    path = TRADES_DIR / "paper_trades.jsonl"
    return _load_jsonl(path)


def load_testnet_trades() -> List[Dict[str, Any]]:
    path = TRADES_DIR / "testnet_trades.jsonl"
    return _load_jsonl(path)


def count_risk_violations(
    max_daily_risk_r: float = 5.0,
    max_trades_per_day: int = 20,
) -> Dict[str, Any]:
    if not DAILY_STATE.exists():
        return {"risk_violations": False, "msg": "no daily state tracking yet"}

    try:
        state = json.loads(DAILY_STATE.read_text())
    except Exception:
        return {"risk_violations": True, "msg": "daily state corrupt"}

    violations: List[str] = []
    if state.get("risk_used_r", 0.0) > max_daily_risk_r:
        violations.append(
            f"risk_used_r={state.get('risk_used_r')} > max_daily_risk_r={max_daily_risk_r}"
        )
    if state.get("n_trades", 0) > max_trades_per_day:
        violations.append(
            f"n_trades={state.get('n_trades')} > max_trades_per_day={max_trades_per_day}"
        )

    return {
        "risk_violations": len(violations) > 0,
        "violations": violations,
    }


def drift_analysis(
    paper: List[Dict[str, Any]],
    testnet: List[Dict[str, Any]],
    max_time_diff_sec: int = 60,
    max_score_diff: float = 0.10,
) -> Dict[str, Any]:
    """
    Grober Drift-Check: Für jeden Testnet-Trade wird versucht,
    einen passenden Paper-Trade zu finden (gleiches Pair, Zeitfenster),
    dann Score-Differenz geprüft.
    """
    if not paper or not testnet:
        return {"drift_detected": True, "msg": "missing paper or testnet trades"}

    mismatches = 0
    checked = 0

    def _parse_ts(t: str) -> datetime:
        # erwartet ISO-Format; falls suffix Z fehlt, klappt das hier trotzdem in der Regel
        return datetime.fromisoformat(t.replace("Z", "+00:00"))

    for t in testnet:
        try:
            t_ts = _parse_ts(t["t"])
        except Exception:
            mismatches += 1
            continue

        p = None
        for x in paper:
            if x.get("pair") != t.get("pair"):
                continue
            try:
                p_ts = _parse_ts(x["t"])
            except Exception:
                continue
            if abs((p_ts - t_ts).total_seconds()) <= max_time_diff_sec:
                p = x
                break

        if not p:
            mismatches += 1
            continue

        checked += 1
        try:
            p_score = float(p["meta"]["score"])
            t_score = float(t["meta"]["score"])
        except Exception:
            mismatches += 1
            continue

        if abs(p_score - t_score) > max_score_diff:
            mismatches += 1

    drift_ratio = mismatches / max(1, checked)

    return {
        "drift_detected": drift_ratio > 0.10,
        "drift_ratio": drift_ratio,
        "checked": checked,
        "mismatches": mismatches,
    }


def run_healthcheck() -> Dict[str, Any]:
    paper = load_paper_trades()
    testnet = load_testnet_trades()

    result: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "paper_trades": len(paper),
        "testnet_trades": len(testnet),
        "paper_vs_testnet_ok": len(testnet) >= 100 and len(paper) >= len(testnet),
    }

    result["risk"] = count_risk_violations()
    result["drift"] = drift_analysis(paper, testnet)

    result["ready_for_live"] = (
        result["paper_vs_testnet_ok"]
        and not result["risk"]["risk_violations"]
        and not result["drift"]["drift_detected"]
    )

    return result


if __name__ == "__main__":
    print(json.dumps(run_healthcheck(), indent=2))
