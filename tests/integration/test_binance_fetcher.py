from data.binance_client import get_ohlcv

def test_fetch_klines_returns_rows():
    rows, _ = get_ohlcv("BTCUSDT", "15m", limit=10)
    assert len(rows) > 0
    assert len(rows[0]) == 7
