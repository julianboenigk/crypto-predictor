# src/exchange/binance_spot_live.py
from __future__ import annotations

import os
import time
import hmac
import hashlib
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

# Standard-Endpoint für Binance Spot Live
BINANCE_LIVE_BASE = os.getenv("BINANCE_LIVE_BASE", "https://api.binance.com")
_TIMEOUT = float(os.getenv("BINANCE_LIVE_TIMEOUT_SEC", "10"))
_MAX_RETRIES = int(os.getenv("BINANCE_LIVE_MAX_RETRIES", "2"))


class BinanceSpotLiveClient:
    """
    Minimaler Client für Binance Spot Live (REST).

    Unterstützt aktuell:
    - create_market_order (MARKET)
    - get_account_info

    Keine Futures, keine Margin, keine OCO/OTOCO.
    ACHTUNG: echter Account, echte Orders.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: Optional[str] = None) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = (base_url or BINANCE_LIVE_BASE).rstrip("/")

    @classmethod
    def from_env(cls) -> "BinanceSpotLiveClient":
        key = os.getenv("BINANCE_LIVE_API_KEY")
        secret = os.getenv("BINANCE_LIVE_API_SECRET")
        if not key or not secret:
            raise RuntimeError("BINANCE_LIVE_API_KEY / BINANCE_LIVE_API_SECRET not set in environment")
        base = os.getenv("BINANCE_LIVE_BASE", BINANCE_LIVE_BASE)
        return cls(key, secret, base)

    def _signed_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if params is None:
            params = {}

        # Binance braucht Timestamp und Signatur über Querystring
        params.setdefault("timestamp", int(time.time() * 1000))
        qs = urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, qs.encode("utf-8"), hashlib.sha256).hexdigest()
        qs = f"{qs}&signature={signature}"

        url = f"{self.base_url}{path}?{qs}"
        headers = {"X-MBX-APIKEY": self.api_key}

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = requests.request(method, url, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    # Fallback, falls Binance mal kein JSON liefert
                    return resp.text
            except Exception as e:
                last_exc = e
                if attempt >= _MAX_RETRIES:
                    raise
                # Einfaches Retry-Backoff
                time.sleep(min(1.0 * (attempt + 1), 5.0))

        if last_exc is not None:
            raise last_exc
        # Sollte praktisch nie erreicht werden
        raise RuntimeError("Unexpected error in BinanceSpotLiveClient._signed_request")

    def create_market_order(self, symbol: str, side: str, quantity: float) -> Any:
        """
        Einfacher MARKET-Order im Spot Live.

        symbol: z.B. "BTCUSDT"
        side: "LONG"/"SHORT" oder "BUY"/"SELL"
        quantity: Base-Asset Menge (z.B. BTC)
        """
        side_up = side.upper()
        if side_up not in ("BUY", "SELL", "LONG", "SHORT"):
            raise ValueError(f"Invalid side: {side}")
        if side_up in ("LONG", "BUY"):
            side_final = "BUY"
        else:
            side_final = "SELL"

        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side_final,
            "type": "MARKET",
            "quantity": quantity,
        }
        return self._signed_request("POST", "/api/v3/order", params)

    def get_account_info(self) -> Any:
        """Für Debugging / Checks im Live-Account."""
        return self._signed_request("GET", "/api/v3/account", {})
