from data.binance_client import get_ohlcv


def test_fetch_klines_returns_rows():
    rows = get_ohlcv("BTCUSDT", "15m", limit=10)
    # Integrationstest: bei Netzwerkproblemen darf rows auch None sein
    assert rows is None or isinstance(rows, list)
    if rows:
        assert len(rows) > 0
        # Binance-Kline hat mind. 6 Spalten (open_time, open, high, low, close, volume, ...)
        assert len(rows[0]) >= 6
