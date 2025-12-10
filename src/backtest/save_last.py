# src/backtest/save_last.py
from __future__ import annotations

import json
import sys
from typing import Optional

from src.backtest.run_latest import run_all
from src.app.main import FINAL_SCORE_MIN
from src.reports.backtest_pnl_summary import (
    load_latest_backtest,
    compute_pnl_summary,
)

# Health Check
try:
    from src.tools.agent_health_check import main as health_check_main
except Exception as e:
    print(f"[WARN] HealthCheck import failed: {e}", file=sys.stderr)
    health_check_main = None


def run_health_check() -> bool:
    """
    Führt den Health Check aus und entscheidet,
    ob der Backtest fortgesetzt werden darf.
    """

    if health_check_main is None:
        print("[HEALTH] WARNING: agent_health_check unavailable → Backtest wird trotzdem ausgeführt.")
        return True

    print("[HEALTH] Running agent health check...")
    report = health_check_main(return_dict=True)

    critical_fail = False

    # --- TechnicalAgent MUSS funktionieren ---
    if not report["technical"]["ok"]:
        critical_fail = True
        print("[HEALTH][CRITICAL] TechnicalAgent failed:", report["technical"])

    # --- LLM Token Limit / Call Limit ---
    if not report["llm_token_limits"]["ok"]:
        critical_fail = True
        print("[HEALTH][CRITICAL] LLM token/call limit reached:", report["llm_token_limits"])

    # --- CryptoNews API nur nötig, wenn ENABLED ---
    import os
    if os.getenv("CRYPTONEWS_ENABLED", "true").lower() == "true":
        if not report["cryptonews_api"]["ok"]:
            critical_fail = True
            print("[HEALTH][CRITICAL] CryptoNews API not working:", report["cryptonews_api"])

    if critical_fail:
        print("[HEALTH] Backtest aborted due to critical component failure.")
        return False

    print("[HEALTH] OK – all critical systems online.")
    return True


def main(score_min: Optional[float] = None) -> None:
    """
    Läuft die neue Backtest-Pipeline (run_all) und gibt danach
    die PnL-Zusammenfassung des neuesten Backtests aus.
    """

    # -------------------------------
    # HEALTH CHECK vorher ausführen
    # -------------------------------
    if not run_health_check():
        sys.exit(1)

    if score_min is None:
        score_min = FINAL_SCORE_MIN

    # 1) Neuen Backtest erzeugen
    run_all(score_min=float(score_min))

    # 2) Neueste Backtest-Datei laden
    bt_data = load_latest_backtest()

    # 3) PnL-Summary berechnen
    summary = compute_pnl_summary(bt_data)

    fname = summary.get("file", "unknown")
    print(f"data/backtests/{fname}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
