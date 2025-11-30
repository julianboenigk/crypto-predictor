from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


# Projekt-Root: .../crypto-predictor
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
BACKTEST_DIR = DATA_DIR / "backtests"
BACKTEST_LOG = DATA_DIR / "backtests.log"


def _load_last_from_log() -> Optional[Dict[str, Any]]:
    """
    Lies die letzte nicht-leere Zeile aus data/backtests.log,
    falls die Datei existiert. Rückgabe: dict oder None.
    """
    if not BACKTEST_LOG.exists():
        return None

    last_line: Optional[str] = None
    with BACKTEST_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                last_line = s

    if not last_line:
        return None

    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return None


def _load_last_from_folder() -> Dict[str, Any]:
    """
    Fallback: nimm die zuletzt erzeugte backtest_*.json aus data/backtests.
    Falls keine Datei vorhanden ist, wird FileNotFoundError geworfen.
    """
    if not BACKTEST_DIR.exists():
        raise FileNotFoundError("data/backtests does not exist")

    files = sorted(
        BACKTEST_DIR.glob("backtest_*.json"),
        key=lambda p: p.name,
    )
    if not files:
        raise FileNotFoundError("No backtest_*.json files in data/backtests")

    last_file = files[-1]
    with last_file.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    # Falls in der alten Datei kein "file"-Key war, ergänzen wir ihn
    payload.setdefault("file", last_file.name)
    return payload


def main() -> None:
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Versuche, die letzte Backtest-Zeile aus backtests.log zu lesen
    payload = _load_last_from_log()

    # 2. Fallback: Nutze die letzte vorhandene backtest_*.json
    if payload is None:
        payload = _load_last_from_folder()

    # Neuen Dateinamen bauen
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = BACKTEST_DIR / f"backtest_{ts}.json"

    # "file"-Feld aktualisieren
    payload = dict(payload)
    payload["file"] = out_path.name

    # Schreiben
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # Konsole: Pfad + Inhalt anzeigen (wie bisher)
    print(out_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
