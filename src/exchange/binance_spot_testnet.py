# src/exchange/binance_spot_testnet.py
from __future__ import annotations

import os
import time
import hmac
import hashlib
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

# Standard-Endpoint für Binance Spot Demo / Testnet
BINANCE_TESTNET_BASE = os.getenv("BINANCE_TESTNET_BASE", "https://demo-api.binance.com")
_TIMEOUT = float(os.getenv("BINANCE_TESTNET_TIMEOUT_SEC", "10"))
_MAX_RETRIES = int(os.getenv("BINANCE_TESTNET_MAX_RETRIES", "2"))


class BinanceSpotTestnetClient:
    """
    Minimaler Client für Binance Spot Testnet (REST).

    Unterstützt aktuell:
    - create_market_order (MARKET)
    - get_account_info

    Keine Futures, keine Margin, keine OCO/OTOCO.
    """

    def __init__(self, api_key: str, api_secret: str, base_url: Optional[str] = None) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = (base_url or BINANCE_TESTNET_BASE).rstrip("/")

    @classmethod
    def from_env(cls) -> "BinanceSpotTestnetClient":
        key = os.getenv("BINANCE_TESTNET_API_KEY")
        secret = os.getenv("BINANCE_TESTNET_API_SECRET")
        if not key or not secret:
            raise RuntimeError("BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET not set in environment")
        base = os.getenv("BINANCE_TESTNET_BASE", BINANCE_TESTNET_BASE)
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
                resp = requests.request(method.upper(), url, headers=headers, timeout=_TIMEOUT)
                if resp.status_code in (418, 429):
                    # Rate Limits: einfacher Backoff
                    time.sleep(min(1.0 * (attempt + 1), 5.0))
                    continue
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    return resp.text
            except Exception as e:
                last_exc = e
                if attempt >= _MAX_RETRIES:
                    raise
                time.sleep(min(1.0 * (attempt + 1), 5.0))

        if last_exc is not None:
            raise last_exc

    def create_market_order(self, symbol: str, side: str, quantity: float) -> Any:
        """
        Einfacher MARKET-Order im Spot Testnet.

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
        """Für Debugging / Checks im Testnet."""
        return self._signed_request("GET", "/api/v3/account", {})
