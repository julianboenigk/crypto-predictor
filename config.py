# === API / Source ===
VS_CURRENCY = "eur"          # cosmetic in messages
# Binance klines (free)
BINANCE_INTERVAL = "1h"      # use 1h for larger swings
BINANCE_LIMIT = 1000

# === Universe ===
# Static fallback list (used if dynamic fetch fails)
COIN_IDS = [
    "bitcoin","ethereum","binancecoin","ripple","solana",
    "cardano","dogecoin","tron","chainlink","litecoin"
]
# Map CoinGecko IDs -> Binance symbols
SYMBOL_MAP = {
    "bitcoin":"BTCUSDT","ethereum":"ETHUSDT","binancecoin":"BNBUSDT","ripple":"XRPUSDT",
    "solana":"SOLUSDT","cardano":"ADAUSDT","dogecoin":"DOGEUSDT","tron":"TRXUSDT",
    "chainlink":"LINKUSDT","litecoin":"LTCUSDT",
}
USE_DYNAMIC_SYMBOLS = True    # turn on dynamic top list
DYNAMIC_TOP_N = 20            # top 20 by 24h quote volume

# === Strategy ===
MIN_EXPECTED_RETURN_PCT = 5.0   # realistic on 1h
MIN_RR = 1.5
DATA_FRESHNESS_SEC = 1800
EMA_LEN = 200
RSI_LEN = 14
ATR_LEN = 14

# === Telegram ===
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

# === Files ===
DATA_DIR = "data"
LOG_FILE = "data/signals.csv"
