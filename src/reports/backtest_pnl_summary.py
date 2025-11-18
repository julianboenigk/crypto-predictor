# src/reports/backtest_pnl_summary.py
from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path
from typing import Any, Dict


def load_latest_backtest() -> Dict[str, Any]:
    files = sorted(glob("data/backtests/backtest_*.json"))
    if not files:
        raise FileNotFoundError("No backtest_*.json files found in data/backtests")
    path = Path(files[-1])
    data = json.loads(path.read_text())
    data["_file"] = path.name
    return data


def _compute_fee_r_per_trade() -> float:
    fee_pct = float(os.getenv("BINANCE_FEE_PCT", "0.001"))
    fee_sides = float(os.getenv("BACKTEST_FEE_SIDES", "2.0"))
    sl_pct = float(os.getenv("BACKTEST_SL_PCT", "0.004"))

    if sl_pct <= 0:
        return 0.0

    roundtrip_fee_pct = fee_pct * fee_sides
    fee_r = roundtrip_fee_pct / sl_pct
    return fee_r


def compute_pnl_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    n_trades = int(data.get("n_trades", 0))
    wins = int(data.get("wins", 0))
    losses = int(data.get("losses", 0))

    rr = float(os.getenv("BACKTEST_RR", "1.5"))
    fee_r_per_trade = _compute_fee_r_per_trade()

    if n_trades == 0:
        return {
            "file": data.get("_file"),
            "n_trades": 0,
            "wins": wins,
            "losses": losses,
            "winrate": None,
            "rr": rr,
            "pnl_r_gross": None,
            "expectancy_r_gross": None,
            "profit_factor_gross": None,
            "fee_r_per_trade": fee_r_per_trade,
            "fee_total_r": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    # --- Brutto ---
    gross_win_r = wins * rr
    gross_loss_r = losses * 1.0
    pnl_r_gross = gross_win_r - gross_loss_r

    winrate = wins / n_trades if n_trades > 0 else None
    expectancy_r_gross = (winrate * rr) - ((1 - winrate) * 1.0)

    profit_factor_gross = (
        gross_win_r / gross_loss_r if gross_loss_r > 0 else None
    )

    # --- Fees in R ---
    fee_total_r = n_trades * fee_r_per_trade

    # --- Netto ---
    pnl_r_net = pnl_r_gross - fee_total_r
    expectancy_r_net = expectancy_r_gross - fee_r_per_trade

    profit_after = wins * (rr - fee_r_per_trade)
    loss_after = losses * (1.0 + fee_r_per_trade)

    profit_factor_net = (
        profit_after / loss_after if loss_after > 0 else None
    )

    return {
        "file": data.get("_file"),
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "rr": rr,
        # Brutto
        "pnl_r_gross": pnl_r_gross,
        "expectancy_r_gross": expectancy_r_gross,
        "profit_factor_gross": profit_factor_gross,
        # Fees
        "fee_r_per_trade": fee_r_per_trade,
        "fee_total_r": fee_total_r,
        # Netto
        "pnl_r": pnl_r_net,
        "expectancy_r": expectancy_r_net,
        "profit_factor": profit_factor_net,
    }


def main() -> None:
    data = load_latest_backtest()
    summary = compute_pnl_summary(data)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
