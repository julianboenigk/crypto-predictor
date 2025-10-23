import time, math
from typing import Dict, List
import requests
import pandas as pd
import config

BINANCE = "https://api.binance.com"

# ---------- HTTP with retry ----------
def _get(path: str, params: dict, tries: int = 3, backoff: float = 0.6) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = requests.get(f"{BINANCE}{path}", params=params, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(backoff * (2 ** i))
    raise last

# ---------- Helpers ----------
STABLES = {"USDT","FDUSD","USDC","BUSD","TUSD","DAI","EUR","TRY"}
def _is_leveraged(sym: str) -> bool:
    # filter tokens like BTCUPUSDT, BTCDOWNUSDT, ... and 5S/5L style
    return any(x in sym for x in ("UPUSDT","DOWNUSDT","BULLUSDT","BEARUSDT","3LUSDT","3SUSDT","4LUSDT","4SUSDT","5LUSDT","5SUSDT"))

def _eurusdt() -> float:
    r = _get("/api/v3/ticker/price", {"symbol": "EURUSDT"})
    return float(r.json()["price"])

def get_top_symbols(n: int) -> List[str]:
    # rank by 24h quoteVolume, keep *USDT spot* and exclude stables/leveraged
    r = _get("/api/v3/ticker/24hr", {})
    rows = []
    for item in r.json():
        sym = item["symbol"]
        if not sym.endswith("USDT"): 
            continue
        base = sym[:-4]
        if base in STABLES or _is_leveraged(sym):
            continue
        try:
            qv = float(item.get("quoteVolume", "0"))
        except:
            qv = 0.0
        rows.append((sym, qv))
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:n]]

# ---------- Markets and OHLC ----------
def get_markets(ids_or_symbols: List[str]) -> pd.DataFrame:
    eurusdt = _eurusdt()
    out = []
    for it in ids_or_symbols:
        sym = config.SYMBOL_MAP.get(it, it)  # allow CoinGecko id or direct symbol
        if not sym.endswith("USDT"): 
            continue
        try:
            r = _get("/api/v3/ticker/price", {"symbol": sym})
            usdt = float(r.json()["price"])
            eur = usdt / eurusdt if eurusdt > 0 else None
            out.append({"key": it, "symbol": sym, "price_eur": eur})
        except Exception:
            continue
    return pd.DataFrame(out)

def _klines(symbol: str) -> pd.DataFrame:
    r = _get("/api/v3/klines", {"symbol": symbol, "interval": config.BINANCE_INTERVAL, "limit": config.BINANCE_LIMIT})
    cols = ["t","o","h","l","c","v","ct","qv","n","tb","tqv","ig"]
    df = pd.DataFrame(r.json(), columns=cols)
    df = df[["t","o","h","l","c"]].astype({"o":"float64","h":"float64","l":"float64","c":"float64"})
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("Europe/Berlin")
    return df

def last_candle_fresh(df: pd.DataFrame) -> bool:
    if df.empty: return False
    period = (df["t"].iloc[-1] - df["t"].iloc[-2]).total_seconds() if len(df) >= 2 else 300
    allowed = max(config.DATA_FRESHNESS_SEC, int(period * 2))
    ts = int(df.iloc[-1]["t"].tz_convert("UTC").timestamp())
    return (time.time() - ts) <= allowed

def get_ohlc(key: str) -> pd.DataFrame:
    sym = config.SYMBOL_MAP.get(key, key)  # id or symbol
    if not sym.endswith("USDT"):
        return pd.DataFrame(columns=["t","o","h","l","c"])
    return _klines(sym)

def load_all_ohlc(keys: List[str]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for key in keys:
        try:
            df = get_ohlc(key)
            if not df.empty and len(df) >= config.EMA_LEN and last_candle_fresh(df):
                out[key] = df
        except Exception:
            continue
    return out
