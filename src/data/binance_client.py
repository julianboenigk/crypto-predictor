from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize any OHLCV dataframe to columns: ['t','o','h','l','c','v'] with numeric dtypes.
    Accepts files with extra columns / different headers, takes first 6 useful columns if needed.
    """
    df = df.copy()

    # If it already contains our canonical columns, select them
    wanted = ["t", "o", "h", "l", "c", "v"]
    lower_cols = [str(c).strip().lower() for c in df.columns]

    # Try to map common headers
    mapping = {}
    for src, dst in [
        ("time", "t"), ("timestamp", "t"), ("open", "o"),
        ("high", "h"), ("low", "l"), ("close", "c"),
        ("volume", "v")
    ]:
        if src in lower_cols:
            mapping[df.columns[lower_cols.index(src)]] = dst
    if mapping:
        df = df.rename(columns=mapping)

    # If canonical columns exist after rename, just keep them
    if all(col in df.columns for col in wanted):
        df = df[wanted]
    else:
        # Fallback: take first 6 columns as t,o,h,l,c,v
        take = list(df.columns)[:6]
        df = df[take]
        df.columns = wanted

    # Enforce numeric
    for c in wanted:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop rows with missing time or close
    df = df.dropna(subset=["t", "c"]).reset_index(drop=True)

    # Make sure time is int
    df["t"] = df["t"].astype(int)

    # Sort by time and drop duplicates
    df = df.sort_values("t").drop_duplicates(subset=["t"], keep="last").reset_index(drop=True)
    return df


class BinanceClient:
    """
    Simple Binance client for OHLCV data fetching and CSV management.
    Uses Binance public API (no auth required).
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "crypto-predictor/1.0"})

    def get_ohlcv(self, symbol: str, interval: str = "15m", limit: int = 500) -> pd.DataFrame:
        url = f"{self.BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
        r = self.session.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        df = pd.DataFrame(
            data,
            columns=[
                "t", "o", "h", "l", "c", "v",
                "_close_time", "_quote_asset_volume", "_trades",
                "_taker_base", "_taker_quote", "_ignore"
            ],
        )
        df = df[["t", "o", "h", "l", "c", "v"]].astype(float)
        df["t"] = df["t"].astype(int)
        return _normalize_df(df)

    def ensure_csv_up_to_date(
        self, pair: str, interval: str = "15m", data_dir: str = "data"
    ) -> Dict[str, Any]:
        """
        Ensures that the CSV for a given pair is up to date by appending
        the latest candles from Binance. Returns {rows_appended, file}.
        Robust to legacy headers/extra columns.
        """
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        f = Path(data_dir) / f"{pair}_{interval}.csv"

        df_new = self.get_ohlcv(pair, interval=interval, limit=500)

        if not f.exists():
            df_new.to_csv(f, index=False)
            return {"rows_appended": len(df_new), "file": str(f)}

        # Load & normalize existing file
        try:
            df_old = pd.read_csv(f)
        except Exception:
            df_old = pd.DataFrame(columns=["t", "o", "h", "l", "c", "v"])
        df_old = _normalize_df(df_old)

        last_ts = int(df_old["t"].iloc[-1]) if not df_old.empty else 0
        df_append = df_new[df_new["t"] > last_ts]

        if not df_append.empty:
            # Ensure canonical header by writing header only once
            df_append.to_csv(f, mode="a", index=False, header=False)
            return {"rows_appended": len(df_append), "file": str(f)}

        # If file header/shape was legacy, rewrite once to canonical
        if list(pd.read_csv(f, nrows=0).columns) != ["t", "o", "h", "l", "c", "v"]:
            # Rewrite normalized (idempotent)
            df_old.to_csv(f, index=False)

        return {"rows_appended": 0, "file": str(f)}

    # Backward compatibility helper (old name)
    def append_latest_csv(
        self, pair: str, interval: str = "15m", data_dir: str = "data"
    ) -> Dict[str, Any]:
        return self.ensure_csv_up_to_date(pair, interval, data_dir)
