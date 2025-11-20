# src/trade/limits.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple

TRADING_DAILY_STATE_FILE = Path("data/trading_daily_state.json")
TRADING_DAILY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_trading_state() -> Dict[str, Any]:
    """
    Tages-State laden oder initialisieren.
    Struktur:
    {
        "date": "YYYY-MM-DD",
        "n_trades": int,
        "risk_used_r": float
    }
    """
    today = _today_str()
    if not TRADING_DAILY_STATE_FILE.exists():
        return {"date": today, "n_trades": 0, "risk_used_r": 0.0}

    try:
        with TRADING_DAILY_STATE_FILE.open("r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        # Defekte Datei: neu beginnen
        return {"date": today, "n_trades": 0, "risk_used_r": 0.0}

    if state.get("date") != today:
        # Neuer Tag -> Reset
        return {"date": today, "n_trades": 0, "risk_used_r": 0.0}

    # Fallbacks
    state.setdefault("n_trades", 0)
    state.setdefault("risk_used_r", 0.0)
    return state


def _save_trading_state(state: Dict[str, Any]) -> None:
    try:
        with TRADING_DAILY_STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        # Fällt im Zweifel still aus, verhindert aber keinen Run
        pass


def check_trading_limits(
    max_trades_per_day: int,
    max_daily_risk_r: float,
    max_risk_per_trade_r: float,
    assumed_r_per_trade: float = 1.0,
) -> Tuple[bool, str]:
    """
    Prüft, ob unter den gegebenen Limits ein weiterer Trade eröffnet werden darf.

    - max_trades_per_day: 0 = deaktiviert
    - max_daily_risk_r: 0.0 = deaktiviert
    - max_risk_per_trade_r: 0.0 = deaktiviert
    - assumed_r_per_trade: aktuell 1R pro Trade (entspricht 1% Konto-Risiko)

    Rückgabe:
        (ok, reason)
        ok = False -> keine neuen Trades eröffnen
    """
    state = _load_trading_state()

    # Sofortiger Block, wenn ein einzelner Trade > max_risk_per_trade_r wäre
    if max_risk_per_trade_r > 0.0 and assumed_r_per_trade > max_risk_per_trade_r:
        return False, (
            f"risk_per_trade_r {assumed_r_per_trade:.2f} > max_risk_per_trade_r "
            f"{max_risk_per_trade_r:.2f}"
        )

    projected_trades = state["n_trades"] + 1
    projected_risk = state["risk_used_r"] + assumed_r_per_trade

    if max_trades_per_day > 0 and projected_trades > max_trades_per_day:
        return False, (
            f"max_trades_per_day reached: {state['n_trades']} trades "
            f"already opened today"
        )

    if max_daily_risk_r > 0.0 and projected_risk > max_daily_risk_r:
        return False, (
            f"max_daily_risk_r reached: {state['risk_used_r']:.2f}R used, "
            f"limit {max_daily_risk_r:.2f}R"
        )

    return True, "limits_ok"


def update_trading_state_after_trade(
    assumed_r_per_trade: float = 1.0,
) -> None:
    """
    Nach einem erfolgreich eröffneten Trade aufrufen.
    """
    state = _load_trading_state()
    state["n_trades"] += 1
    state["risk_used_r"] += float(assumed_r_per_trade)
    _save_trading_state(state)
