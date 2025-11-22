from __future__ import annotations

import json
import os
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

# .env laden, damit TELEGRAM_* und andere Settings verfügbar sind
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception:
    send_telegram = None  # type: ignore


DATA_DIR = Path("data")
# Wichtig: wir werten nur ABGESCHLOSSENE Paper-Trades aus
PAPER_TRADES_PATH = DATA_DIR / "paper_trades_closed.jsonl"
TESTNET_TRADES_PATH = DATA_DIR / "testnet_trades.jsonl"


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------

def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def _parse_ts(raw: Any) -> datetime | None:
    """
    Versucht, einen Zeitstempel aus einem Trade zu parsen.
    Unterstützt mehrere Feldnamen und ISO-Formate.
    """
    if raw is None:
        return None
    s = str(raw)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def _load_trades(path: Path) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    if not path.exists():
        return trades
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trades.append(json.loads(line))
                except Exception:
                    # Schlechte Zeile ignorieren
                    continue
    except Exception:
        # Falls Datei korrupt oder nicht lesbar ist: leere Liste zurück
        return []
    return trades


def _filter_last_24h(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)

    filtered: List[Dict[str, Any]] = []
    for tr in trades:
        ts = (
            _parse_ts(tr.get("exit_time"))
            or _parse_ts(tr.get("t"))
            or _parse_ts(tr.get("time"))
            or _parse_ts(tr.get("closed_at"))
        )
        if ts is None:
            continue
        if ts >= cutoff:
            filtered.append(tr)

    return filtered


def _classify_outcome(tr: Dict[str, Any]) -> Tuple[bool | None, float]:
    """
    Liefert (is_win, pnl_r).

    - is_win: True/False oder None wenn nicht bestimmbar
    - pnl_r: float (0.0 wenn nicht vorhanden/parsing-fehler)
    """
    # pnl_r versuchen zu lesen
    pnl_r = 0.0
    raw_pnl = tr.get("pnl_r", tr.get("r", None))
    if raw_pnl is not None:
        try:
            pnl_r = float(raw_pnl)
        except Exception:
            pnl_r = 0.0

    outcome = tr.get("outcome")
    status = str(tr.get("status", "")).lower()

    # Outcome-Feld (z.B. "TP"/"SL"/"MANUAL")
    if isinstance(outcome, str):
        o = outcome.upper()
        if o == "TP":
            return True, pnl_r
        if o == "SL":
            return False, pnl_r

    # Heuristik über Status
    if "win" in status:
        return True, pnl_r
    if "loss" in status or "lose" in status:
        return False, pnl_r

    # Heuristik über pnl_r
    if pnl_r > 0:
        return True, pnl_r
    if pnl_r < 0:
        return False, pnl_r

    # weder noch bestimmbar
    return None, pnl_r


def compute_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Berechnet einfache Kennzahlen über eine Liste von Trades.
    Erwartet, dass `pnl_r` (oder `r`) pro Trade vorhanden ist,
    arbeitet aber robust gegen fehlende Felder.
    """
    if not trades:
        return {
            "n_trades": 0,
            "wins": 0,
            "losses": 0,
            "unknown": 0,
            "winrate": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    n_trades = len(trades)
    wins = 0
    losses = 0
    unknown = 0
    pnl_values: List[float] = []

    for tr in trades:
        is_win, pnl_r = _classify_outcome(tr)
        pnl_values.append(pnl_r)
        if is_win is True:
            wins += 1
        elif is_win is False:
            losses += 1
        else:
            unknown += 1

    pnl_total = sum(pnl_values)
    winrate = wins / n_trades if n_trades > 0 else None
    expectancy_r = pnl_total / n_trades if n_trades > 0 else None

    gross_win_r = sum(v for v in pnl_values if v > 0)
    gross_loss_r = -sum(v for v in pnl_values if v < 0)
    profit_factor = gross_win_r / gross_loss_r if gross_loss_r > 0 else None

    return {
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "winrate": winrate,
        "pnl_r": pnl_total,
        "expectancy_r": expectancy_r,
        "profit_factor": profit_factor,
    }


def build_message(
    stats_paper: Dict[str, Any],
    stats_testnet: Dict[str, Any] | None = None,
) -> str:
    """
    Kompakte, nicht-technische Zusammenfassung für Telegram.
    Fokus: letzte 24h, reale Performance.
    """
    now = datetime.now(UTC)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = []
    lines.append("📊 Live Trading – letzte 24h")
    lines.append(f"Stand: {date_str}")
    lines.append("")

    # --- Paper ---
    lines.append("Paper-Trades (letzte 24h):")
    lines.append(f"- Anzahl Trades: {stats_paper['n_trades']}")
    lines.append(
        f"- Wins: {stats_paper['wins']}, Losses: {stats_paper['losses']}, "
        f"Unbekannt: {stats_paper['unknown']}"
    )
    lines.append(f"- Trefferquote: {_fmt_pct(stats_paper['winrate'])}")
    lines.append(f"- Ergebnis: {_fmt_float(stats_paper['pnl_r'], 1)} R")
    lines.append(
        f"- Erwartungswert: {_fmt_float(stats_paper['expectancy_r'], 3)} R/Trade"
    )
    lines.append(
        f"- Profit Factor: {_fmt_float(stats_paper['profit_factor'], 2)}"
    )

    # --- Testnet (optional) ---
    if stats_testnet is not None:
        lines.append("")
        lines.append("Testnet-Trades (letzte 24h):")
        lines.append(f"- Anzahl Trades: {stats_testnet['n_trades']}")
        lines.append(
            f"- Wins: {stats_testnet['wins']}, Losses: {stats_testnet['losses']}, "
            f"Unbekannt: {stats_testnet['unknown']}"
        )
        lines.append(f"- Trefferquote: {_fmt_pct(stats_testnet['winrate'])}")
        lines.append(f"- Ergebnis: {_fmt_float(stats_testnet['pnl_r'], 1)} R")
        lines.append(
            f"- Erwartungswert: {_fmt_float(stats_testnet['expectancy_r'], 3)} R/Trade"
        )
        lines.append(
            f"- Profit Factor: {_fmt_float(stats_testnet['profit_factor'], 2)}"
        )

    lines.append("")
    lines.append(
        "Hinweis: Es werden nur abgeschlossene Trades mit verfügbarem Ergebnis (R) berücksichtigt."
    )

    return "\n".join(lines)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    # Trades laden
    paper_trades = _load_trades(PAPER_TRADES_PATH)
    testnet_trades = _load_trades(TESTNET_TRADES_PATH)

    # Auf letzte 24h filtern (Exit-Zeitpunkt)
    paper_24h = _filter_last_24h(paper_trades)
    testnet_24h = _filter_last_24h(testnet_trades) if testnet_trades else []

    stats_paper = compute_stats(paper_24h)
    stats_testnet = compute_stats(testnet_24h) if testnet_24h else None

    # JSON-Output für Logs/stdout
    summary = {
        "run_at": datetime.now(UTC).isoformat(),
        "paper": stats_paper,
        "testnet": stats_testnet,
    }
    print(json.dumps(summary, indent=2))

    # Wenn in den letzten 24h überhaupt keine Trades abgeschlossen wurden:
    has_trades_24h = stats_paper["n_trades"] > 0 or (
        stats_testnet is not None and stats_testnet["n_trades"] > 0
    )

    send_flag = os.getenv("TELEGRAM_LIVE_SUMMARY", "true").lower() == "true"

    if not has_trades_24h:
        # Keine Telegram-Nachricht, nur Log
        return

    if send_telegram is not None and send_flag:
        msg = build_message(stats_paper, stats_testnet)
        if len(msg) > 3500:
            msg = msg[:3400] + "\n\n[gekürzt]"
        send_telegram(msg)


if __name__ == "__main__":
    main()
