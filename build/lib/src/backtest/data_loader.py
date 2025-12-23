from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any


# ---------------------------------------------------------------------
# Binance liefert KL-Daten als LISTEN:
# [ open_time, open, high, low, close, volume, ... ]
#
# Die Engine erwartet DICTS:
# { "t": ts, "o":..., "h":..., "low":..., "c":..., "v":... }
#
# Diese Datei normalisiert ALLE historischen Daten.
# ---------------------------------------------------------------------


def normalize_binance_row(row: list) -> Dict[str, Any]:
    """
    Binance-Kerze normalisieren (list → dict).
    row = [
        0: open_time_ms,
        1: open,
        2: high,
        3: low,
        4: close,
        5: volume,
        6: close_time,
        7: quote_volume,
        8: trades,
        9: taker_buy_base,
        10: taker_buy_quote,
        11: ignore
    ]
    """
    return {
        "t": row[0] / 1000.0,       # Sekunden
        "o": float(row[1]),
        "h": float(row[2]),
        "low": float(row[3]),
        "c": float(row[4]),
        "v": float(row[5]),
    }


def load_pair_history(pair: str, interval: str) -> List[Dict[str, Any]]:
    """
    Lädt historical data aus data/historical/*.jsonl
    und normalisiert jede Zeile auf dict-Format.
    """
    path = Path(f"data/historical/{pair}_{interval}.jsonl")
    if not path.exists():
        raise FileNotFoundError(f"No historical file found: {path}")

    candles = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)

            # Wenn die Zeile bereits dict ist → übernehmen
            if isinstance(row, dict):
                # Du hast bereits frühere Dict-Versionen gespeichert
                # Wir stellen sicher, dass die Keys vorhanden sind
                if "c" in row and "h" in row:
                    candles.append(row)
                    continue

            # → sonst: Binance Rohformat → normalisieren
            if isinstance(row, list):
                norm = normalize_binance_row(row)
                candles.append(norm)
                continue

            # Fallback (Fehlerhafte Zeile überspringen)
            continue

    return candles
